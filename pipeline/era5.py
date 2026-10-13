"""
Daily temperatures for the pipeline, from the ERA5 point time series
(reanalysis-era5-single-levels-timeseries), the dataset the validation ran
on.

Two downloads per city:
- the archive, ARCHIVE_YEARS, fetched once and kept (the same file the
  validation and the tests use);
- the recent period, from the year after the archive to today, fetched again
  on every run. ERA5 is about 5 days behind, and the newest day can arrive
  incomplete or as empty values, so only days with all 24 hourly values are
  used, and only up to the first gap.
"""

import datetime

import pandas as pd

from validation.cds_fetch import (RAW_DATA_DIR, daily_extremes, fetch_point_timeseries,
                                  read_hourly, timeseries_file)

ARCHIVE_YEARS = (1940, 2024)
RECENT_START = datetime.date(ARCHIVE_YEARS[1] + 1, 1, 1)
DATASET = "reanalysis-era5-single-levels-timeseries"


def archive_daily(client, city):
    """Daily Tmax/Tmin for the archive years."""
    if client is None and not timeseries_file(city["key"], *ARCHIVE_YEARS).exists():
        raise SystemExit(f"{city['name']}: no ERA5 archive on disk; run without --offline")
    return fetch_point_timeseries(client, city["key"], city["lat"], city["lon"], *ARCHIVE_YEARS)


def recent_file(city):
    return RAW_DATA_DIR / "timeseries" / f"{city['slug']}_recent_t2m.zip"


def download_recent(client, city, today):
    """Fetch hourly temperatures from RECENT_START to today, replacing the last download."""
    zip_file = recent_file(city)
    zip_file.parent.mkdir(parents=True, exist_ok=True)
    request = {
        "variable": ["2m_temperature"],
        "location": {"longitude": city["lon"], "latitude": city["lat"]},
        "date": [f"{RECENT_START.isoformat()}/{today.isoformat()}"],
        "data_format": "csv",
    }
    print(f"  {city['name']}: fetching {request['date'][0]}...")
    client.retrieve(DATASET, request, str(zip_file))


def recent_daily(city):
    """Daily Tmax/Tmin from RECENT_START up to the latest usable day, from
    the download on disk."""
    return usable_days(read_hourly(recent_file(city)))


def usable_days(hourly):
    """
    Daily Tmax/Tmin for the unbroken run of complete days that starts on
    RECENT_START.

    A day counts only if all 24 of its hourly values are present. The series
    ends at the first day that does not: the model counts days by position,
    so a hole must end the series, never be skipped over.
    """
    if hourly["valid_time"].duplicated().any():
        raise ValueError("duplicate hours in the ERA5 download")
    daily = daily_extremes(hourly, full_days_only=True)
    daily = daily.sort_values("date").reset_index(drop=True)
    expected = pd.Timestamp(RECENT_START) + pd.to_timedelta(daily.index, unit="D")
    daily = daily[(daily["date"] == expected).cummin()]
    if daily.empty:
        raise ValueError(f"no complete day from {RECENT_START} in the ERA5 download")
    return daily
