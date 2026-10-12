"""
Inputs for comparing our SI-x implementation with USA-NPN's code.

Two sets:
- synthetic temperature series, generated here from a fixed seed, so the
  comparison runs on a fresh clone with no downloads;
- the ERA5 series the app itself uses, for every validation city and year,
  when they have been downloaded (data/raw/timeseries/).

Each set is identified by a checksum of its temperatures. The reference
outputs in tests/fixtures/ record the checksum they were computed for, so a
test can tell "the inputs changed" apart from "the model disagrees".
"""

import contextlib
import hashlib
import io

import numpy as np

from validation.cds_fetch import fetch_point_timeseries, timeseries_file
from validation.config import VALIDATION_LOCATIONS
from validation.reference_fetch import NETWORKS

# USA-NPN's production script gives the model days 1-240 of the year.
N_DAYS = 240
N_SYNTHETIC = 500
SEED = 20261011
ERA5_FIRST_YEAR, ERA5_LAST_YEAR = 1940, 2024

PLANTS = ("lilac", "arnoldred", "zabelli")


def checksum(*arrays):
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(np.round(np.asarray(array, dtype="<f8"), 4).tobytes())
    return digest.hexdigest()


def _edge_cases():
    """Series built to hit the model's special cases."""
    day = np.arange(N_DAYS)
    warming = -12 + 30 * day / N_DAYS

    cases = []
    # Latitudes around the switch between the two day-length formulas, and
    # far enough north for the day length to hit its 1 h and 23 h limits.
    for lat in (39.99, 40.0, 40.01, 60.0, 66.5, 70.0, 75.0):
        cases.append((lat, warming + 5, warming - 5))
    # Days with no daily range (tmax == tmin).
    cases.append((48.0, warming.copy(), warming.copy()))
    # Never warm enough: no leaf, no bloom.
    cases.append((55.0, np.full(N_DAYS, -5.0), np.full(N_DAYS, -15.0)))
    # Warm from January 1: leaf within the first days.
    cases.append((30.0, np.full(N_DAYS, 22.0), np.full(N_DAYS, 12.0)))
    # A maximum below the previous day's minimum, and the reverse.
    tmax, tmin = warming + 5, warming - 5
    tmax[100], tmin[101] = tmin[99] - 3, tmax[100] + 20
    cases.append((50.0, tmax, tmin))
    # Minimum of exactly 0 °F, which the model nudges to 0.01.
    zero_f = -160 / 9
    assert zero_f * 1.8 + 32 == 0.0
    tmin = warming - 5
    tmin[20:25] = zero_f
    cases.append((45.0, warming + 5, tmin))
    return cases


def synthetic_cases():
    """[(lat, tmax_c, tmin_c)]: N_SYNTHETIC random series plus edge cases.

    RandomState, not default_rng: its stream is guaranteed stable across
    NumPy versions. Values are rounded to 0.01 °C so that last-digit
    differences between platforms cannot change the inputs.
    """
    rng = np.random.RandomState(SEED)
    day = np.arange(N_DAYS)
    cases = []
    for _ in range(N_SYNTHETIC):
        lat = round(float(rng.uniform(25, 70)), 2)
        mean = rng.uniform(-8, 18)
        amplitude = rng.uniform(4, 16)
        noise_sd = rng.uniform(1, 5)
        half_range = rng.uniform(1.5, 7) * rng.uniform(0.4, 1.6, N_DAYS)

        noise = np.empty(N_DAYS)
        shocks = rng.normal(0, noise_sd, N_DAYS)
        noise[0] = shocks[0]
        for i in range(1, N_DAYS):
            noise[i] = 0.7 * noise[i - 1] + shocks[i]

        tmean = mean - amplitude * np.cos(2 * np.pi * (day - 15) / 365) + noise
        cases.append((lat, np.round(tmean + half_range, 2), np.round(tmean - half_range, 2)))
    return cases + _edge_cases()


def synthetic_checksum(cases):
    return checksum(*[np.concatenate(([lat], tmax, tmin)) for lat, tmax, tmin in cases])


def era5_locations():
    """Validation cities with an open lilac network: (name, lat, lon)."""
    return [(name, lat, lon) for name, lat, lon, _zone in VALIDATION_LOCATIONS
            if name.split(", ")[-1] in NETWORKS]


def era5_daily(location, lat, lon):
    """Daily Tmax/Tmin from the cached ERA5 download, or None if absent."""
    if not timeseries_file(location, ERA5_FIRST_YEAR, ERA5_LAST_YEAR).exists():
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        return fetch_point_timeseries(None, location, lat, lon, ERA5_FIRST_YEAR, ERA5_LAST_YEAR)


def era5_years(daily):
    """{year: (tmax_c, tmin_c)} for every full year in a daily series."""
    years = {}
    for year, days in daily.groupby(daily["date"].dt.year):
        days = days.sort_values("date")
        if days["date"].iloc[0].dayofyear == 1 and len(days) >= N_DAYS:
            years[int(year)] = (days["tmax_c"].to_numpy(), days["tmin_c"].to_numpy())
    return years
