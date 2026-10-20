#!/usr/bin/env python3
"""
Multi-year test of the SI-x bloom index against observed lilac first bloom.

For every validation city covered by an open lilac network (DWD, SLU),
for every year in the range that the network covers (Germany from 1951,
Sweden from 2008; see validation/reference_fetch.py):
1. fetch hourly ERA5 2m temperature at the nearest grid point (one CDS
   request per city), reduce to daily Tmax/Tmin;
2. run the unmodified SI-x model;
3. compare with the median observed lilac first-bloom date nearby.

Nothing is fitted. Two questions:
- Absolute accuracy: how many days off is the predicted bloom date?
- Anomalies: does the model get the year-to-year deviations right? The
  app shows "X days earlier/later than usual", so this is the number that
  matters. Each city's mean (model and observed separately) is removed and
  the remaining anomalies compared. The benchmark is a model that predicts
  "a normal year" every year, whose anomaly error is the observed
  variability itself.

The report also says how sure these numbers are (validation/bloom_stats.py):
confidence intervals from resampling whole years and whole cities, the
result per country and per period, the long-term trend, and the result with
each city left out.

Usage:
    python run_bloom_test.py [--start 1951] [--end 2024]
"""

import argparse

import numpy as np
import pandas as pd

from validation import bloom_stats
from validation.cds_fetch import fetch_point_timeseries, get_cds_client
from validation.config import BASE_DIR, DATA_DIR, VALIDATION_LOCATIONS
from validation.reference_fetch import NETWORKS, build_bloom_references
from validation.si_x_model import predict_spring_index

# The report goes to the private docs repo, a sibling of this one.
REPORT_FILE = BASE_DIR.parent / "call-of-kiuru-docs" / "docs" / "bloom_multiyear.md"

# ERA5 is fetched from its first year whatever the test period, so the same
# download serves the pipeline's baseline and trend chart.
ERA5_FIRST_YEAR = 1940


def predict_bloom(daily, lat, year):
    """SI-x bloom (index and lilac sub-model) for one site-year, or None."""
    days = daily[daily["date"].dt.year == year].sort_values("date")
    if days.empty or days["date"].iloc[0].dayofyear != 1:
        return None
    result = predict_spring_index(days["tmax_c"].values, days["tmin_c"].values, lat)
    return result["bloom"]["average"], result["bloom"]["lilac"]


def error_stats(errors):
    errors = pd.Series(errors, dtype=float).dropna()
    return {
        "n": len(errors),
        "rmse": float(np.sqrt((errors ** 2).mean())),
        "mae": float(errors.abs().mean()),
        "bias": float(errors.mean()),
    }


def anomaly_stats(df, model_col):
    """Compare per-city anomalies (value minus that city's mean)."""
    grouped = df.groupby("location")
    model_anom = df[model_col] - grouped[model_col].transform("mean")
    obs_anom = df["observed"] - grouped["observed"].transform("mean")

    rmse = float(np.sqrt(((model_anom - obs_anom) ** 2).mean()))
    null_rmse = float(np.sqrt((obs_anom ** 2).mean()))
    # Years that were clearly early or late (3+ days from the city's mean).
    clear = obs_anom.abs() >= 3
    return {
        "n": len(df),
        "r": float(np.corrcoef(model_anom, obs_anom)[0, 1]),
        "rmse": rmse,
        "null_rmse": null_rmse,
        "skill": 1 - (rmse / null_rmse) ** 2,
        "sign_agree": float((np.sign(model_anom[clear]) == np.sign(obs_anom[clear])).mean()),
        "n_clear": int(clear.sum()),
    }


def per_city_table(df):
    rows = []
    for location, g in df.groupby("location"):
        e = error_stats(g["model"] - g["observed"])
        model_anom = g["model"] - g["model"].mean()
        obs_anom = g["observed"] - g["observed"].mean()
        rows.append({
            "location": location,
            "years": len(g),
            "median_n_obs": g["n_obs"].median(),
            "rmse": e["rmse"],
            "bias": e["bias"],
            "anomaly_r": float(np.corrcoef(model_anom, obs_anom)[0, 1]),
            "observed_sd": float(g["observed"].std(ddof=0)),
        })
    return pd.DataFrame(rows)


UNCERTAINTY_ROWS = [
    ("RMSE (days)", "rmse", ".1f"),
    ("Bias (days)", "bias", "+.1f"),
    ("Anomaly correlation", "anomaly_r", ".2f"),
    ("Anomaly RMSE (days)", "anomaly_rmse", ".1f"),
    ("Skill", "skill", ".2f"),
]


def interval(bounds, fmt):
    return f"{bounds[0]:{fmt}} to {bounds[1]:{fmt}}"


def uncertainty_lines(df):
    """Report sections on how sure the pooled numbers are."""
    pooled = bloom_stats.overall(df)
    n_years, n_cities = df["year"].nunique(), df["location"].nunique()
    lines = [
        "",
        "## Uncertainty",
        "",
        "The city-years are not independent. Observed anomalies correlate",
        f"{bloom_stats.cross_city_correlation(df):.2f} on average between cities in the same year, so this is",
        f"closer to {n_years} independent springs than to {len(df)} tests. The 95% intervals",
        "therefore resample whole years, or whole cities, with replacement",
        f"({bloom_stats.N_RESAMPLES:,} resamples, percentile intervals). With {n_years} years and",
        f"{n_cities} cities they are approximate; read the wider of the two.",
        "",
        "| Statistic | Estimate | 95% interval, resampling years | 95% interval, resampling cities |",
        "|---|---|---|---|",
    ]
    for label, key, fmt in UNCERTAINTY_ROWS:
        lines.append(f"| {label} | {pooled['estimate'][key]:{fmt}} | "
                     f"{interval(pooled['by_year'][key], fmt)} | "
                     f"{interval(pooled['by_city'][key], fmt)} |")

    lines += [
        "",
        "## By country",
        "",
        "Intervals from resampling years within the country.",
        "",
        "| Country | Cities | City-years | RMSE | Bias | Anomaly correlation | Anomaly RMSE | Normal-year RMSE | Skill |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in bloom_stats.by_country(df):
        ci = c["interval"]
        lines.append(
            f"| {c['country']} | {c['cities']} | {c['n']} | {c['rmse']:.1f} | {c['bias']:+.1f} | "
            f"{c['anomaly_r']:.2f} ({interval(ci['anomaly_r'], '.2f')}) | "
            f"{c['anomaly_rmse']:.1f} ({interval(ci['anomaly_rmse'], '.1f')}) | "
            f"{c['normal_year_rmse']:.1f} | {c['skill']:.2f} ({interval(ci['skill'], '.2f')}) |")

    gap = (df["model_lilac"] - df["model"]).mean()
    lines += [
        "",
        "## Index vs its lilac component",
        "",
        "SI-x averages three plants: a lilac and two honeysuckles. The app shows",
        "that published index. The observations are lilac only, so the index's",
        "lilac component is the like-for-like comparison. On average it predicts",
        f"bloom {gap:.1f} days later than the index.",
        "",
        "| Subset | Model | City-years | RMSE | Bias | Anomaly correlation | Anomaly RMSE | Skill |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in bloom_stats.index_vs_lilac(df):
        lines.append(f"| {r['subset']} | {r['model']} | {r['n']} | {r['rmse']:.1f} | "
                     f"{r['bias']:+.1f} | {r['anomaly_r']:.2f} | {r['anomaly_rmse']:.1f} | "
                     f"{r['skill']:.2f} |")

    lines += [
        "",
        "## By period",
        "",
        "Does the result hold in every part of the record? Anomalies here are",
        "against each period's own city means. 1979 is the start of the",
        "satellite era, before which ERA5 has fewer observations to draw on.",
        "Periods with fewer than 10 years of data for a country are left out.",
        "",
        "| Country | Period | Years | City-years | RMSE | Bias | Anomaly correlation | Anomaly RMSE | Normal-year RMSE | Skill |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in bloom_stats.by_period(df):
        ci = p["interval"]
        lines.append(
            f"| {p['country']} | {p['first_year']}–{p['last_year']} | {p['years']} | {p['n']} | "
            f"{p['rmse']:.1f} | {p['bias']:+.1f} | "
            f"{p['anomaly_r']:.2f} ({interval(ci['anomaly_r'], '.2f')}) | "
            f"{p['anomaly_rmse']:.1f} ({interval(ci['anomaly_rmse'], '.1f')}) | "
            f"{p['normal_year_rmse']:.1f} | {p['skill']:.2f} ({interval(ci['skill'], '.2f')}) |")

    trends = bloom_stats.trends(df)
    if trends:
        lines += [
            "",
            "## Long-term trend",
            "",
            "Linear trend of bloom day, in days per decade (negative = earlier),",
            "for cities with at least 30 years. With each city's trend removed from",
            "both model and observations, the anomaly correlation is",
            f"{bloom_stats.detrended_correlation(df):.2f}: the model tracks single years, not only the drift.",
            "",
            "| City | Years | Model trend | Observed trend |",
            "|---|---|---|---|",
        ]
        for t in trends:
            lines.append(f"| {t['location']} | {t['years']} | {t['model']:+.1f} | "
                         f"{t['observed']:+.1f} |")

    lines += [
        "",
        "## Leaving one city out",
        "",
        "The pooled numbers with each city removed in turn. Nothing is refitted",
        "(the model has no fitted parameters); this shows how much the result",
        "leans on any one city.",
        "",
        "| Without | City-years | RMSE | Bias | Anomaly correlation | Anomaly RMSE | Skill |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in bloom_stats.leave_one_city_out(df):
        lines.append(f"| {r['without']} | {r['n']} | {r['rmse']:.1f} | {r['bias']:+.1f} | "
                     f"{r['anomaly_r']:.2f} | {r['anomaly_rmse']:.1f} | {r['skill']:.2f} |")
    return lines, pooled


def write_report(df, start, end):
    overall = error_stats(df["model"] - df["observed"])
    lilac = error_stats(df["model_lilac"] - df["observed"])
    anom = anomaly_stats(df, "model")
    robust = df[df["n_obs"] >= 3]
    anom_robust = anomaly_stats(robust, "model")
    cities = per_city_table(df)
    country = df["location"].str.split(", ").str[-1]
    decades = df.assign(error=df["model"] - df["observed"], country=country,
                        decade=df["year"] // 10 * 10).pivot_table(
        index="decade", columns="country", values="error", aggfunc=["mean", "count"])
    coverage = ", ".join(f"{name} {g['year'].min()}–{g['year'].max()}"
                         for name, g in df.groupby(country))

    def anomaly_row(label, a):
        return (f"| {label} | {a['n']} | {a['r']:.2f} | {a['rmse']:.1f} | "
                f"{a['null_rmse']:.1f} | {a['skill']:.2f} | "
                f"{a['sign_agree']:.0%} of {a['n_clear']} |")

    lines = [
        "# SI-x bloom: multi-year test",
        "",
        f"Generated by `run_bloom_test.py` for {start}–{end} ({coverage}). SI-x bloom index,",
        "unmodified (published coefficients), vs median observed lilac (*Syringa vulgaris*)",
        "first bloom near each city: DWD phase 5 within 0.5°, SLU phase 53 within 1°.",
        "ERA5 hourly 2m temperature at the nearest grid point. Nothing fitted.",
        "Positive error = model late.",
        "",
        "The countries cover different periods, so the pooled figures are dominated",
        "by the longer record. Read the by-country and by-period tables first.",
        "",
        "## Absolute accuracy",
        "",
        "| Model | City-years | RMSE (days) | MAE | Bias |",
        "|---|---|---|---|---|",
        f"| SI-x bloom index (3-plant average) | {overall['n']} | {overall['rmse']:.1f} | "
        f"{overall['mae']:.1f} | {overall['bias']:+.1f} |",
        f"| SI-x lilac sub-model | {lilac['n']} | {lilac['rmse']:.1f} | "
        f"{lilac['mae']:.1f} | {lilac['bias']:+.1f} |",
        "",
        "## Year-to-year anomalies",
        "",
        "Each city's mean removed from both model and observations. *Normal-year",
        "RMSE* is the error of always predicting the city's average date; *skill*",
        "is the share of that variance the model explains (1 = perfect, 0 = no",
        "better than predicting a normal year). *Direction* counts years at least",
        "3 days early or late where the model gets the direction right.",
        "",
        "| Subset | City-years | Correlation | Anomaly RMSE | Normal-year RMSE | Skill | Direction |",
        "|---|---|---|---|---|---|---|",
        anomaly_row("All", anom),
        anomaly_row("≥3 observations", anom_robust),
        "",
        "## Per city",
        "",
        "| City | Years | Median obs/year | RMSE | Bias | Anomaly correlation | Observed SD |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, c in cities.sort_values("location").iterrows():
        lines.append(f"| {c['location']} | {c['years']} | {c['median_n_obs']:.0f} | "
                     f"{c['rmse']:.1f} | {c['bias']:+.1f} | {c['anomaly_r']:.2f} | "
                     f"{c['observed_sd']:.1f} |")
    grades = bloom_stats.city_grades(df)
    grades.to_csv(DATA_DIR / "bloom_grades.csv", index=False)
    lines += [
        "",
        "## Grade per city",
        "",
        f"For the site (rule in PLAN.md §3): cities with at least {bloom_stats.MIN_SPRINGS} "
        "springs, graded by the low end of the 95% interval of the anomaly "
        "correlation, resampling that city's years: strong ≥ 0.8, moderate ≥ 0.5, "
        "weak below. Typical miss is the anomaly RMSE; calling every spring "
        "normal is the observed SD.",
        "",
        "| City | Springs | Median obs/year | Anomaly correlation | Typical miss | Calling every spring normal | Grade |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, g in grades.sort_values("location").iterrows():
        lines.append(f"| {g['location']} | {g['springs']} | {g['median_n_obs']:.0f} | "
                     f"{g['anomaly_r']:.2f} ({g['anomaly_r_low']:.2f} to {g['anomaly_r_high']:.2f}) | "
                     f"{g['anomaly_rmse']:.1f} | {g['normal_year_rmse']:.1f} | {g['grade']} |")
    countries = list(decades["mean"].columns)
    lines += [
        "",
        "## Mean error by decade",
        "",
        "Mean error in days, with the number of city-years in brackets.",
        "",
        "| Decade | " + " | ".join(countries) + " |",
        "|---|" + "---|" * len(countries),
    ]
    for decade, row in decades.iterrows():
        cells = [f"{row['mean'][c]:+.1f} ({int(row['count'][c])})"
                 if pd.notna(row["mean"][c]) else "" for c in countries]
        lines.append(f"| {decade}s | " + " | ".join(cells) + " |")
    uncertainty, pooled = uncertainty_lines(df)
    lines += uncertainty

    REPORT_FILE.write_text("\n".join(lines) + "\n")
    print(f"✓ Wrote {REPORT_FILE}")
    return overall, anom, anom_robust, cities, pooled


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--start", type=int, default=1951)
    parser.add_argument("--end", type=int, default=2024)
    args = parser.parse_args()

    locations = [loc for loc in VALIDATION_LOCATIONS
                 if loc[0].split(", ")[-1] in NETWORKS]

    print(f"Building lilac bloom references {args.start}-{args.end}...")
    references = build_bloom_references(args.start, args.end)
    references.to_csv(DATA_DIR / "bloom_references.csv", index=False)
    print(f"  {len(references)} city-years with observations")

    print("Fetching ERA5 point time series...")
    client = get_cds_client()
    predictions = []
    for location, lat, lon, _zone in locations:
        daily = fetch_point_timeseries(client, location, lat, lon, ERA5_FIRST_YEAR, args.end)
        for year in range(args.start, args.end + 1):
            bloom = predict_bloom(daily, lat, year)
            if bloom:
                predictions.append({"location": location, "year": year,
                                    "model": bloom[0], "model_lilac": bloom[1]})
    predictions = pd.DataFrame(predictions)

    df = predictions.merge(
        references.rename(columns={"doy": "observed"}), on=["location", "year"])
    df = df.dropna(subset=["model", "observed"])
    df.to_csv(DATA_DIR / "bloom_multiyear.csv", index=False)

    overall, anom, anom_robust, cities, pooled = write_report(df, args.start, args.end)
    print(f"\nAbsolute: RMSE {overall['rmse']:.1f} d, MAE {overall['mae']:.1f}, "
          f"bias {overall['bias']:+.1f} (n={overall['n']})")
    print(f"Anomalies: r={anom['r']:.2f}, RMSE {anom['rmse']:.1f} d vs normal-year "
          f"{anom['null_rmse']:.1f} d, skill {anom['skill']:.2f}")
    print(f"  (≥3 obs: r={anom_robust['r']:.2f}, skill {anom_robust['skill']:.2f}, "
          f"n={anom_robust['n']})")
    print(f"95% intervals, resampling years: r {interval(pooled['by_year']['anomaly_r'], '.2f')}, "
          f"RMSE {interval(pooled['by_year']['rmse'], '.1f')} d")
    print(cities.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
