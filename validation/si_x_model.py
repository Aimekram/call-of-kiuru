"""
Extended Spring Index (SI-x) Growing-Degree-Day Model.

A phenology model for predicting leaf-out (budburst) timing based on daily
temperature data. Adapted from the USA-NPN model and European research.

Reference:
- Schwartz, M. D., Ault, T. R., & Pulso, S. L. (2013). "Common sense" 
  phenology. Frontiers in Ecology and Evolution, 1, 9.
- European research: leaf-out more sensitive to daytime max temperature
  than to flat daily mean.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from .config import (
    SI_X_BASE_TEMP,
    SI_X_MIN_TEMP,
    SI_X_MAX_TEMP,
    SI_X_SPRING_START_DOY,
    SI_X_GDD_THRESHOLD,
    SI_X_MAX_TEMP_WEIGHT,
    SI_X_MEAN_TEMP_WEIGHT,
)


def compute_gdd_single_day(tmax_c, tmin_c, base_temp=SI_X_BASE_TEMP, 
                           max_weight=SI_X_MAX_TEMP_WEIGHT,
                           mean_weight=SI_X_MEAN_TEMP_WEIGHT):
    """
    Compute growing degree days (GDD) for a single day.
    
    Accounts for:
    - Minimum temperature cutoff (can't accumulate below SI_X_MIN_TEMP)
    - Maximum temperature cap (can't exceed SI_X_MAX_TEMP)
    - European weighting: max temperature more predictive of leaf-out
    
    Args:
        tmax_c: Maximum daily temperature (°C)
        tmin_c: Minimum daily temperature (°C)
        base_temp: Base temperature threshold (default 10°C)
        max_weight: Proportion of max temp to use (default 0.7)
        mean_weight: Proportion of mean temp to use (default 0.3)
    
    Returns:
        GDD accumulated for this day (float)
    """
    # Clamp to physical bounds
    tmin_c = max(tmin_c, SI_X_MIN_TEMP)
    tmax_c = min(tmax_c, SI_X_MAX_TEMP)
    
    # If max is below base, no GDD
    if tmax_c < base_temp:
        return 0.0
    
    # Compute mean temperature
    tmean_c = (tmax_c + tmin_c) / 2.0
    
    # European model: weight toward max temperature
    # (Research shows leaf-out more sensitive to daytime warmth)
    effective_temp = (tmax_c * max_weight) + (tmean_c * mean_weight)
    
    # GDD is accumulated above base temperature
    gdd = max(0.0, effective_temp - base_temp)
    
    return gdd


def predict_leaf_out_doy(daily_tmax_c, daily_tmin_c, gdd_threshold=SI_X_GDD_THRESHOLD,
                         spring_start_doy=SI_X_SPRING_START_DOY):
    """
    Predict day-of-year (DOY) of leaf-out for a single year.
    
    Accumulates growing degree days starting from spring_start_doy (late Feb),
    and returns the DOY on which GDD accumulation crosses the threshold.
    
    Args:
        daily_tmax_c: Array of daily max temperatures (°C) for the year
        daily_tmin_c: Array of daily min temperatures (°C) for the year
        gdd_threshold: GDD threshold for leaf-out (default 130)
        spring_start_doy: Day-of-year to begin accumulation (default 59 = Feb 28/29)
    
    Returns:
        Day-of-year (1-366) when leaf-out occurs, or None if threshold not reached
    """
    if len(daily_tmax_c) < spring_start_doy:
        return None
    
    gdd_accumulation = 0.0
    
    for doy in range(spring_start_doy, len(daily_tmax_c)):
        # Day-of-year is 1-indexed; array is 0-indexed
        tmax = daily_tmax_c[doy - 1]
        tmin = daily_tmin_c[doy - 1]
        
        # Skip if invalid data
        if pd.isna(tmax) or pd.isna(tmin):
            continue
        
        daily_gdd = compute_gdd_single_day(tmax, tmin)
        gdd_accumulation += daily_gdd
        
        if gdd_accumulation >= gdd_threshold:
            # Leaf-out occurs on this DOY
            return doy
    
    # Threshold not reached in this year
    return None


def compute_baseline(historical_years_predictions):
    """
    Compute the median leaf-out DOY across a reference period (e.g., 1991-2020).
    
    Args:
        historical_years_predictions: List/array of DOY predictions for each year
    
    Returns:
        Median DOY (int), or None if insufficient data
    """
    valid_doys = [doy for doy in historical_years_predictions if doy is not None]
    
    if not valid_doys:
        return None
    
    return np.median(valid_doys)


def compute_anomaly(current_doy, baseline_doy):
    """
    Compute how many days earlier (negative) or later (positive) than baseline.
    
    Args:
        current_doy: Current year's predicted leaf-out DOY
        baseline_doy: Baseline (1991-2020 median) DOY
    
    Returns:
        Anomaly in days (negative = earlier, positive = later)
    """
    if current_doy is None or baseline_doy is None:
        return None
    
    return current_doy - baseline_doy


class SIxModel:
    """
    SI-x phenology model for a single location.
    Encapsulates data and predictions for easier tracking.
    """
    
    def __init__(self, location_name, lat, lon, climate_zone):
        self.location_name = location_name
        self.lat = lat
        self.lon = lon
        self.climate_zone = climate_zone
        
        # Data: year -> {tmax: array, tmin: array}
        self.daily_temps = {}
        
        # Predictions: year -> doy
        self.leaf_out_doys = {}
        
        # Baseline
        self.baseline_doy = None
    
    def add_year_data(self, year, daily_tmax_c, daily_tmin_c):
        """Add temperature data for a single year."""
        self.daily_temps[year] = {
            "tmax": daily_tmax_c,
            "tmin": daily_tmin_c,
        }
    
    def predict_all_years(self):
        """Run SI-x model on all loaded years."""
        for year, temps in self.daily_temps.items():
            doy = predict_leaf_out_doy(temps["tmax"], temps["tmin"])
            self.leaf_out_doys[year] = doy
    
    def compute_baseline_and_anomalies(self, baseline_start_year, baseline_end_year):
        """
        Compute the baseline (median DOY 1991-2020) and anomalies for all years.
        
        Args:
            baseline_start_year: Start of baseline period
            baseline_end_year: End of baseline period
        """
        baseline_years = [
            doy for year, doy in self.leaf_out_doys.items()
            if baseline_start_year <= year <= baseline_end_year
        ]
        
        self.baseline_doy = compute_baseline(baseline_years)
        
        # Compute anomalies
        self.anomalies = {}
        for year, doy in self.leaf_out_doys.items():
            self.anomalies[year] = compute_anomaly(doy, self.baseline_doy)
    
    def get_summary(self, year):
        """
        Get a summary dict for a specific year.
        
        Returns:
            {
                "location": str,
                "lat": float,
                "lon": float,
                "climate_zone": str,
                "year": int,
                "leaf_out_doy": int or None,
                "baseline_doy": int or None,
                "anomaly_days": float or None,
            }
        """
        return {
            "location": self.location_name,
            "lat": self.lat,
            "lon": self.lon,
            "climate_zone": self.climate_zone,
            "year": year,
            "leaf_out_doy": self.leaf_out_doys.get(year),
            "baseline_doy": self.baseline_doy,
            "anomaly_days": self.anomalies.get(year) if hasattr(self, "anomalies") else None,
        }
