"""
Extended Spring Index (SI-x) first-leaf model.

Independent implementation of the published SI-x leaf and bloom models:
- Schwartz, Ault & Betancourt (2013), International Journal of Climatology:
  regression coefficients.
- Ault et al. (2015): methodology, including the 637 GDH synoptic threshold.
- Izquierdo-Verdiguier & Zurita-Milla (2024), Scientific Data, Table 1:
  all six leaf/bloom equations in one place.
The published threshold is ">= 1000"; USA-NPN's code uses ">= 999.5"
(i.e. rounded), which is what is used here. Output was checked against
USA-NPN's production code (github.com/usa-npn/gridded_models) and matches it
exactly; that repo has no license file, so none of its code is copied here.

Input is daily Tmax/Tmin starting on January 1. The model runs in Fahrenheit
with a 31°F base, and returns the first-leaf day of year for each of three
indicator plants (lilac, Arnold Red honeysuckle, Zabel honeysuckle) plus
their average, which is what USA-NPN publishes as the SI-x leaf index.

Caveats for use in Europe:
- The day-length formula and regression coefficients were fitted on US data
  (roughly 25-49°N). Applying them at 55-60°N is an extrapolation.
- The index predicts first leaf of lilac/honeysuckle, not of native European
  trees.
"""

import numpy as np

from .config import SI_X_BASE_TEMP_F

PLANTS = ("lilac", "arnoldred", "zabelli")

# SI-x leaf regression: mdsum1 = a*mds0 + b*synop + c*dde2 + d*dd57
_LEAF_COEFFICIENTS = {
    "lilac": (3.306, 13.878, 0.201, 0.153),
    "arnoldred": (4.266, 20.899, 0.000, 0.248),
    "zabelli": (2.802, 21.433, 0.266, 0.000),
}
_LEAF_SYNOPTIC_LIMIT = 637
# SI-x bloom regression, accumulated from the day after first leaf:
# mdsum1 = a*days_since_leaf + b*accumulated_gdh
_BLOOM_COEFFICIENTS = {
    "lilac": (-23.934, 0.116),
    "arnoldred": (-24.825, 0.127),
    "zabelli": (-11.368, 0.096),
}
_TRIGGER = 999.5


def _solar_day_index(day):
    """Day index used by the SI-x day-length formula (day 0 = Jan 1)."""
    return ((day + 306) % 366) + 1


def _day_length_hours(day, lat):
    if lat < 40:
        length = 12.14 + 3.34 * np.tan(np.radians(lat)) * np.cos(
            0.0172 * _solar_day_index(day) - 1.95)
    else:
        length = 12.25 + (1.6164 + 1.7643 * np.tan(np.radians(lat)) ** 2) * np.cos(
            0.0172 * _solar_day_index(day) - 1.95)
    return min(max(length, 1), 23)


def growing_degree_hours(tmax_f, tmin_f, lat, base_temp_f=SI_X_BASE_TEMP_F):
    """Daily growing degree hours from daily Tmax/Tmin (°F), via SI-x's
    sine (daytime) / logarithmic (night) hourly temperature approximation."""
    tmax = np.array(tmax_f, dtype=float)
    tmin = np.array(tmin_f, dtype=float)

    # Same continuity adjustment as USA-NPN's gridded spring_index().
    for day in range(1, len(tmax)):
        tmax[day] = max(tmax[day], tmin[day - 1])
        tmin[day] = min(tmin[day], tmax[day - 1])

    tmin[tmin == 0] = 0.01
    tmax[tmax == tmin] += 0.01

    gdh = np.empty(len(tmax))
    for day in range(len(tmax)):
        day_length = _day_length_hours(day, lat)
        daylight_hours = int(day_length)
        diff = tmax[day] - tmin[day]

        total = max(tmin[day] - base_temp_f, 0)
        for hour in range(1, daylight_hours + 1):
            temp = diff * np.sin(np.pi / (day_length + 4) * hour) + tmin[day]
            total += max(temp - base_temp_f, 0)

        sunset_temp = diff * np.sin(np.pi / (day_length + 4) * day_length) + tmin[day]
        if sunset_temp <= 0:
            sunset_temp = 0.01
        for count, _hour in enumerate(range(daylight_hours + 1, 24), start=1):
            temp = sunset_temp - (sunset_temp - tmin[day]) / np.log(24 - day_length) * np.log(count)
            total += max(temp - base_temp_f, 0)

        gdh[day] = total
    return gdh


def first_leaf_doy(gdh, plant):
    """SI-x first-leaf day of year (1-based) for one plant, or None if the
    threshold isn't reached within the data."""
    a, b, c, d = _LEAF_COEFFICIENTS[plant]
    lag = [gdh[0], gdh[0], 0, 0, 0, 0, 0]
    synop = 0

    for day, hours in enumerate(gdh):
        dde2 = hours + lag[0] + lag[1]
        dd57 = sum(lag[4:7])
        if dde2 >= _LEAF_SYNOPTIC_LIMIT:
            synop += 1

        mdsum1 = a * day + b * synop + c * dde2 + d * dd57
        if mdsum1 >= _TRIGGER:
            # USA-NPN reports Arnold Red one day later than the trigger day.
            out_day = day + 1 if plant == "arnoldred" else day
            return out_day + 1

        lag[1:7] = lag[0:6]
        lag[0] = hours
    return None


def first_bloom_doy(gdh, plant, leaf_doy):
    """SI-x first-bloom day of year (1-based) for one plant, or None.

    Like USA-NPN, the leaf DOY is used directly as the 0-based start index,
    so accumulation begins the day after first leaf."""
    if leaf_doy is None:
        return None
    a, b = _BLOOM_COEFFICIENTS[plant]
    agdh = 0
    for day in range(leaf_doy, len(gdh)):
        agdh += gdh[day]
        if a * (day - leaf_doy) + b * agdh >= _TRIGGER:
            return day + 1
    return None


def predict_leaf_out(tmax_c, tmin_c, lat):
    """
    Run SI-x leaf on one site-year.

    Args:
        tmax_c, tmin_c: daily temperatures (°C), index 0 = January 1.
            Trailing NaNs (days not yet fetched) are ignored; gaps before
            that are not allowed.
        lat: site latitude (degrees north)

    Returns:
        {"lilac": doy, "arnoldred": doy, "zabelli": doy, "average": doy},
        with None where a plant doesn't reach first leaf in the data.
    """
    return predict_spring_index(tmax_c, tmin_c, lat)["leaf"]


def predict_spring_index(tmax_c, tmin_c, lat):
    """
    Run SI-x leaf and bloom on one site-year (same inputs as predict_leaf_out).

    Returns:
        {"leaf": {plant: doy, ..., "average": doy},
         "bloom": {plant: doy, ..., "average": doy}}
    """
    tmax_c = np.asarray(tmax_c, dtype=float)
    tmin_c = np.asarray(tmin_c, dtype=float)

    valid = ~(np.isnan(tmax_c) | np.isnan(tmin_c))
    if not valid[0]:
        raise ValueError("SI-x needs data starting January 1")
    n_days = int(np.argmin(valid)) if not valid.all() else len(valid)
    if valid[n_days:].any():
        raise ValueError("Temperature series has gaps; SI-x needs continuous daily data")

    gdh = growing_degree_hours(tmax_c[:n_days] * 1.8 + 32, tmin_c[:n_days] * 1.8 + 32, lat)

    leaf = {plant: first_leaf_doy(gdh, plant) for plant in PLANTS}
    bloom = {plant: first_bloom_doy(gdh, plant, leaf[plant]) for plant in PLANTS}
    for result in (leaf, bloom):
        doys = [result[p] for p in PLANTS]
        result["average"] = None if None in doys else float(np.mean(doys))
    return {"leaf": leaf, "bloom": bloom}


def compute_baseline(historical_years_predictions):
    """Median leaf-out DOY across a reference period, or None."""
    valid_doys = [doy for doy in historical_years_predictions if doy is not None]
    if not valid_doys:
        return None
    return np.median(valid_doys)


def compute_anomaly(current_doy, baseline_doy):
    """Days earlier (negative) or later (positive) than baseline."""
    if current_doy is None or baseline_doy is None:
        return None
    return current_doy - baseline_doy


class SIxModel:
    """SI-x leaf predictions for a single location."""

    def __init__(self, location_name, lat, lon, climate_zone):
        self.location_name = location_name
        self.lat = lat
        self.lon = lon
        self.climate_zone = climate_zone
        self.daily_temps = {}
        self.leaf_out_doys = {}
        self.plant_doys = {}
        self.bloom_doys = {}
        self.baseline_doy = None
        self.anomalies = {}

    def add_year_data(self, year, daily_tmax_c, daily_tmin_c):
        self.daily_temps[year] = {"tmax": daily_tmax_c, "tmin": daily_tmin_c}

    def predict_all_years(self):
        for year, temps in self.daily_temps.items():
            result = predict_spring_index(temps["tmax"], temps["tmin"], self.lat)
            self.plant_doys[year] = result["leaf"]
            self.leaf_out_doys[year] = result["leaf"]["average"]
            self.bloom_doys[year] = result["bloom"]

    def compute_baseline_and_anomalies(self, baseline_start_year, baseline_end_year):
        baseline_years = [
            doy for year, doy in self.leaf_out_doys.items()
            if baseline_start_year <= year <= baseline_end_year
        ]
        self.baseline_doy = compute_baseline(baseline_years)
        self.anomalies = {
            year: compute_anomaly(doy, self.baseline_doy)
            for year, doy in self.leaf_out_doys.items()
        }
