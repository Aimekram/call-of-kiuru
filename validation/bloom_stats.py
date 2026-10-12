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


def by_country(df):
    """Estimates per country, with intervals from resampling years."""
    rows = []
    for country, group in df.groupby(df["location"].str.split(", ").str[-1]):
        model, observed = to_matrices(group)
        rows.append({"country": country, "cities": group["location"].nunique(),
                     **summary(model, observed),
                     "interval": block_bootstrap(model, observed, "year")})
    return rows


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
