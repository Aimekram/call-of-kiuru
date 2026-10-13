"""
From daily temperatures to what the site shows: the modelled start of spring
(SI-x first bloom index) per city and year, each city's 1991-2020 average,
and the difference from it.

The model is validation/si_x_model.py, unchanged. Nothing here forecasts: a
year has a bloom day only once the temperatures up to that day are in.
Nothing here rounds either: values stay as computed, and are rounded only
where they are displayed.
"""

import pandas as pd

from validation.si_x_model import predict_spring_index

BASELINE_YEARS = (1991, 2020)


def bloom_by_year(daily, lat):
    """
    {year: bloom day of year, or None if not reached in the data} for every
    year whose data starts on January 1.
    """
    result = {}
    for year, days in daily.groupby(daily["date"].dt.year):
        days = days.sort_values("date")
        if days["date"].iloc[0].dayofyear != 1:
            continue
        if (days["date"].diff().dropna() != pd.Timedelta(days=1)).any():
            raise ValueError(f"{year}: daily temperatures have a gap")
        index = predict_spring_index(days["tmax_c"].to_numpy(), days["tmin_c"].to_numpy(), lat)
        result[int(year)] = index["bloom"]["average"]
    return result


def baseline(bloom):
    """Mean bloom day over BASELINE_YEARS. Every year must be present."""
    first, last = BASELINE_YEARS
    days = [bloom.get(year) for year in range(first, last + 1)]
    if None in days:
        missing = [y for y, d in zip(range(first, last + 1), days) if d is None]
        raise ValueError(f"no bloom day for baseline years {missing}")
    return sum(days) / len(days)


def city_result(city, archived, recent):
    """
    One city's entry and rows for the output.

    archived: {year: bloom day} for the archive years.
    recent: daily temperatures from the year after the archive, as returned
        by era5.usable_days.

    The current year is the year of the last day of data. It is "bloomed"
    once the model has reached bloom in the data received, "not_yet" before.
    Rows hold only years with a bloom day.
    """
    overlap = set(archived) & set(recent["date"].dt.year)
    if overlap:
        raise ValueError(f"years in both the archive and the recent data: {sorted(overlap)}")
    by_year = {**archived, **bloom_by_year(recent, city["lat"])}
    normal = baseline(by_year)

    last_day = recent["date"].max().date()
    day = by_year.get(last_day.year)
    current = {"year": last_day.year, "status": "not_yet" if day is None else "bloomed",
               "data_through": last_day.isoformat()}
    if day is not None:
        current.update(bloom_doy=day, days_vs_baseline=day - normal)

    entry = {**{k: city[k] for k in ("slug", "name", "country", "lat", "lon")},
             "baseline_doy": normal, "current": current}
    rows = [{"city": city["slug"], "year": year, "bloom_doy": day,
             "days_vs_baseline": day - normal}
            for year, day in sorted(by_year.items()) if day is not None]
    return entry, rows
