"""
Uncertainty of the multi-year bloom test (run_bloom_test.py).

The city-years are not independent: cities share each year's weather, and
each city keeps its own bias from year to year. So the confidence intervals
resample whole years, or whole cities, never single city-years (a block
bootstrap, percentile intervals). With 15 years and 8 cities the intervals
are approximate, and if anything too narrow.

Nothing here changes the model or its output; these are checks on the
comparison with observations.
"""

import numpy as np
import pandas as pd

METRICS = ["rmse", "bias", "anomaly_r", "anomaly_rmse", "normal_year_rmse", "skill"]
N_RESAMPLES = 10000
SEED = 0

# Periods reported separately. 1979 is the start of the satellite era;
# before it ERA5 has fewer observations to draw on. 2010-2024 is the window
# the test was first run on.
PERIODS = [(1951, 1978), (1979, 2009), (2010, 2024)]


def to_matrices(df):
    """City x year arrays of modelled and observed bloom day (NaN = no data)."""
    model = df.pivot(index="location", columns="year", values="model")
    observed = df.pivot(index="location", columns="year", values="observed")
    return model.to_numpy(dtype=float), observed.to_numpy(dtype=float)


def summary(model, observed):
    """
    Headline statistics from city x year arrays, defined as in
    run_bloom_test.py: anomalies are each city's values minus that city's
    mean, for model and observations separately.
    """
    valid = ~np.isnan(model) & ~np.isnan(observed)
    model = np.where(valid, model, np.nan)
    observed = np.where(valid, observed, np.nan)
    error = (model - observed)[valid]
    model_anom = (model - np.nanmean(model, axis=1, keepdims=True))[valid]
    obs_anom = (observed - np.nanmean(observed, axis=1, keepdims=True))[valid]

    anomaly_rmse = float(np.sqrt(((model_anom - obs_anom) ** 2).mean()))
    normal_year_rmse = float(np.sqrt((obs_anom ** 2).mean()))
    return {
        "n": int(valid.sum()),
        "rmse": float(np.sqrt((error ** 2).mean())),
        "bias": float(error.mean()),
        "anomaly_r": float(np.corrcoef(model_anom, obs_anom)[0, 1]),
        "anomaly_rmse": anomaly_rmse,
        "normal_year_rmse": normal_year_rmse,
        "skill": 1 - (anomaly_rmse / normal_year_rmse) ** 2,
    }


def block_bootstrap(model, observed, by, n_resamples=N_RESAMPLES, seed=SEED):
    """
    95% percentile intervals for every metric, resampling whole years
    (by="year") or whole cities (by="city") with replacement. A city drawn
    twice counts as two cities; a year drawn twice counts twice towards each
    city's mean.
    """
    axis = {"city": 0, "year": 1}[by]
    size = model.shape[axis]
    rng = np.random.default_rng(seed)
    draws = np.empty((n_resamples, len(METRICS)))
    for i in range(n_resamples):
        pick = rng.integers(0, size, size)
        stats = summary(np.take(model, pick, axis=axis), np.take(observed, pick, axis=axis))
        draws[i] = [stats[m] for m in METRICS]
    low, high = np.percentile(draws, [2.5, 97.5], axis=0)
    return {m: (float(low[j]), float(high[j])) for j, m in enumerate(METRICS)}


def overall(df):
    """Estimates with intervals from resampling years and from resampling cities."""
    model, observed = to_matrices(df)
    return {
        "estimate": summary(model, observed),
        "by_year": block_bootstrap(model, observed, "year"),
        "by_city": block_bootstrap(model, observed, "city"),
    }


def by_country_estimates(df):
    """Estimates per country."""
    rows = []
    for country, group in df.groupby(df["location"].str.split(", ").str[-1]):
        rows.append({"country": country, "cities": group["location"].nunique(),
                     "first_year": int(group["year"].min()),
                     "last_year": int(group["year"].max()),
                     **summary(*to_matrices(group))})
    return rows


def by_country(df):
    """Estimates per country, with intervals from resampling years."""
    rows = by_country_estimates(df)
    for row in rows:
        group = df[df["location"].str.endswith(", " + row["country"])]
        row["interval"] = block_bootstrap(*to_matrices(group), "year")
    return rows


# Grades for the site, from the low end of each city's 95% interval of the
# skill: 1 - MSE / MSE of guessing the city's average spring, on anomalies
# (Murphy 1988, Monthly Weather Review 116, Case I, the sample mean as the
# reference; the constant offset is removed, since the site compares each
# city with the model's own average). Resampling that city's years. Revised
# 2026-10-20 from the anomaly correlation with cut-offs 0.8 / 0.5; see
# PLAN.md §3.
#   good:        low end >= 0.5, well ahead of that guess (half its squared error or less)
#   fair:        low end > 0, better than that guess
#   unconfirmed: not shown to be better than that guess
# (Named strong / moderate / weak until 2026-10-20; "weak" read as a verdict
# that the model fails, when the local check is only inconclusive.)
MIN_SPRINGS = 10
GOOD_SKILL = 0.5


def grade(low):
    if low >= GOOD_SKILL:
        return "good"
    return "fair" if low > 0 else "unconfirmed"


def city_grades(df):
    """Per city: springs checked, median observers, skill and anomaly
    correlation with their intervals, typical miss against calling every
    spring normal, and the grade. Cities with fewer than MIN_SPRINGS springs
    are left out."""
    rows = []
    for location, group in df.groupby("location"):
        if len(group) < MIN_SPRINGS:
            continue
        model, observed = to_matrices(group)
        estimate = summary(model, observed)
        interval = block_bootstrap(model, observed, "year")
        rows.append({"location": location, "springs": len(group),
                     "first_year": int(group["year"].min()), "last_year": int(group["year"].max()),
                     "median_n_obs": float(group["n_obs"].median()),
                     "skill": estimate["skill"],
                     "skill_low": interval["skill"][0], "skill_high": interval["skill"][1],
                     "anomaly_r": estimate["anomaly_r"],
                     "anomaly_r_low": interval["anomaly_r"][0], "anomaly_r_high": interval["anomaly_r"][1],
                     "anomaly_rmse": estimate["anomaly_rmse"],
                     "normal_year_rmse": estimate["normal_year_rmse"],
                     "grade": grade(interval["skill"][0])})
    return pd.DataFrame(rows)


def index_vs_lilac(df):
    """The published 3-plant bloom index and its lilac component, each
    compared with the same lilac observations, pooled and per country. The
    app shows the index; the component is reported because the observations
    are lilac, so it is the like-for-like comparison."""
    country = df["location"].str.split(", ").str[-1]
    rows = []
    for label, group in [("All", df)] + list(df.groupby(country)):
        for name, column in (("3-plant index", "model"), ("Lilac component", "model_lilac")):
            model, observed = to_matrices(group.assign(model=group[column]))
            rows.append({"subset": label, "model": name, **summary(model, observed)})
    return rows


def by_period(df, periods=PERIODS, min_years=10):
    """Estimates per country and period, with intervals from resampling
    years. Anomalies are taken against each period's own city means, so a
    period stands on its own. Periods with fewer than min_years years of
    data for a country are skipped."""
    rows = []
    for country, group in df.groupby(df["location"].str.split(", ").str[-1]):
        for first, last in periods:
            part = group[group["year"].between(first, last)]
            if part["year"].nunique() < min_years:
                continue
            model, observed = to_matrices(part)
            rows.append({"country": country, "first_year": first, "last_year": last,
                         "years": part["year"].nunique(), **summary(model, observed),
                         "interval": block_bootstrap(model, observed, "year")})
    return rows


def trends(df, min_years=30):
    """Linear trend of modelled and observed bloom day per city, in days per
    decade, for cities with at least min_years years."""
    rows = []
    for location, group in df.groupby("location"):
        if len(group) < min_years:
            continue
        rows.append({
            "location": location, "years": len(group),
            "model": float(np.polyfit(group["year"], group["model"], 1)[0] * 10),
            "observed": float(np.polyfit(group["year"], group["observed"], 1)[0] * 10),
        })
    return rows


def detrended_correlation(df, min_years=30):
    """Anomaly correlation after removing each city's linear trend from model
    and observations: does the model track single years, not just the
    long-term drift? Cities with at least min_years years."""
    model, observed = [], []
    for _location, group in df.groupby("location"):
        if len(group) < min_years:
            continue
        for column, out in (("model", model), ("observed", observed)):
            fit = np.polyfit(group["year"], group[column], 1)
            out.extend(group[column] - np.polyval(fit, group["year"]))
    if not model:
        return None
    return float(np.corrcoef(model, observed)[0, 1])


def leave_one_city_out(df):
    """Estimates with each city removed in turn. Nothing is refitted: the
    model has no fitted parameters, so this only shows how much the pooled
    numbers lean on any one city."""
    rows = []
    for location in sorted(df["location"].unique()):
        model, observed = to_matrices(df[df["location"] != location])
        rows.append({"without": location, **summary(model, observed)})
    return rows


def cross_city_correlation(df):
    """Mean correlation between cities of observed anomalies in the same year."""
    observed = df.pivot(index="year", columns="location", values="observed")
    corr = (observed - observed.mean()).corr().to_numpy()
    return float(corr[np.triu_indices_from(corr, k=1)].mean())
