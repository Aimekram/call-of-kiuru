"""
Fetch daily temperature data from Copernicus CDS for validation locations.
Uses ERA5 derived single-level daily statistics.
"""

import cdsapi
import os
from pathlib import Path
from .config import (
    RAW_DATA_DIR,
    VALIDATION_LOCATIONS,
    HISTORICAL_START_YEAR,
    HISTORICAL_END_YEAR,
)


def get_cds_client():
    """
    Initialize CDS API client.
    Expects CDS API key to be set in:
    1. Environment variable CDS_API_KEY
    2. ~/.cdsapirc file (default cdsapi location)
    """
    # cdsapi will auto-discover ~/.cdsapirc or use env variables
    try:
        client = cdsapi.Client()
        return client
    except Exception as e:
        print(f"Error initializing CDS client: {e}")
        print("Make sure your CDS API credentials are configured.")
        print("See: https://cds.climate.copernicus.eu/api-how-to")
        raise


def fetch_location_data(client, location_name, lat, lon, start_year, end_year):
    """
    Fetch daily min/max temperature data for a location from CDS.
    
    Fetches only spring months (Feb-May) to reduce CDS cost.
    For phenology validation, we only need the period when leaf-out occurs.
    
    Args:
        client: CDS API client
        location_name: Human-readable name (e.g., "Berlin, Germany")
        lat: Latitude
        lon: Longitude
        start_year: Start year (inclusive)
        end_year: End year (inclusive)

    Returns:
        Dict mapping statistic ("maximum"/"minimum") to a list of monthly
        output file paths (one per year/month requested).
    """
    # Safe filename
    safe_name = location_name.lower().replace(", ", "_").replace(" ", "_")

    print(f"\nFetching data for {location_name} ({lat}, {lon})")
    print(f"Period: {start_year}-{end_year} (Jan-June)")

    # SI-x accumulates heat from January 1, and nordic locations can leaf
    # out as late as June, so Jan-June covers the whole leaf-out window.
    # This reduces CDS cost significantly while preserving full winter-to-spring data for model
    #
    # CDS queues requests spanning more than one month in a heavily congested
    # "large request" tier (capped at 40 concurrent, thousands queued). Splitting
    # into one request per year/month keeps each request in the fast tier.
    #
    # Despite requesting data_format "grib", this dataset actually returns
    # netCDF (HDF5) files. netCDF files can't be concatenated by simply
    # appending bytes the way GRIB messages can, so each month is kept as
    # its own file rather than merged into one.
    output_files = {"maximum": [], "minimum": []}
    try:
        for statistic in output_files:
            print(f"  Fetching daily {statistic}...")
            for year in range(start_year, end_year + 1):
                for month in ["01", "02", "03", "04", "05", "06"]:
                    output_file = (
                        RAW_DATA_DIR / f"{safe_name}_{year}-{month}_{statistic}.nc"
                    )
                    if output_file.exists():
                        print(f"    {year}-{month}... (already downloaded)")
                        output_files[statistic].append(output_file)
                        continue

                    request = {
                        "product_type": "reanalysis",
                        "variable": "2m_temperature",
                        "year": [str(year)],
                        "month": [month],
                        "day": [str(d).zfill(2) for d in range(1, 32)],
                        "daily_statistic": f"daily_{statistic}",
                        "frequency": "1_hourly",
                        "time_zone": "utc+00:00",
                        # CDS area order is north, west, south, east. Keep the request local.
                        "area": [lat + 0.25, lon - 0.25, lat - 0.25, lon + 0.25],
                        "grid": [0.25, 0.25],
                        "data_format": "netcdf",
                    }
                    print(f"    {year}-{month}...")
                    client.retrieve(
                        "derived-era5-single-levels-daily-statistics", request, str(output_file)
                    )
                    output_files[statistic].append(output_file)
            print(f"  ✓ Downloaded {len(output_files[statistic])} monthly files")
        return output_files
    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        raise


def timeseries_file(location_name, start_year, end_year):
    """Where fetch_point_timeseries keeps its download for one location."""
    safe_name = location_name.lower().replace(", ", "_").replace(" ", "_")
    return RAW_DATA_DIR / "timeseries" / f"{safe_name}_{start_year}-{end_year}_t2m.zip"


def read_hourly(zip_file):
    """Hourly 2m temperature (K) from a time-series download: valid_time, t2m."""
    import zipfile

    import pandas as pd

    with zipfile.ZipFile(zip_file) as archive:
        csv_name = next(n for n in archive.namelist() if n.endswith(".csv"))
        with archive.open(csv_name) as f:
            return pd.read_csv(f, parse_dates=["valid_time"])


def daily_extremes(hourly, full_days_only=False):
    """
    Daily Tmax/Tmin (°C) over UTC days from hourly 2m temperature (K), as
    date, tmax_c, tmin_c. With full_days_only, days with fewer than 24
    hourly values are dropped, e.g. the last day of a download that ends
    part-way through it.
    """
    hours = hourly.groupby(hourly["valid_time"].dt.normalize())["t2m"]
    daily = hours.agg(tmax_c="max", tmin_c="min") - 273.15
    if full_days_only:
        daily = daily[hours.count() == 24]
    return daily.rename_axis("date").reset_index()


def fetch_point_timeseries(client, location_name, lat, lon, start_year, end_year):
    """
    Fetch hourly 2m temperature at the nearest ERA5 grid point for a whole
    multi-year period in a single request, and return daily Tmax/Tmin.

    Uses reanalysis-era5-single-levels-timeseries, which serves point
    extractions quickly (~30 s for 15 years), instead of one
    daily-statistics request per month. Daily max/min are taken over UTC
    days, as in the daily-statistics requests above. For Berlin 2020 the two
    agree to 0.1°C on average (SD 0.17°C); the daily-statistics files
    average a 3x3 box, this is the nearest grid point.

    Returns:
        DataFrame with columns: date, tmax_c, tmin_c
    """
    zip_file = timeseries_file(location_name, start_year, end_year)
    zip_file.parent.mkdir(parents=True, exist_ok=True)

    if zip_file.exists():
        print(f"  {location_name}: {zip_file.name} (already downloaded)")
    else:
        print(f"  {location_name}: fetching {start_year}-{end_year} hourly 2m temperature...")
        request = {
            "variable": ["2m_temperature"],
            "location": {"longitude": lon, "latitude": lat},
            "date": [f"{start_year}-01-01/{end_year}-12-31"],
            "data_format": "csv",
        }
        client.retrieve("reanalysis-era5-single-levels-timeseries", request, str(zip_file))

    return daily_extremes(read_hourly(zip_file))


def fetch_all_validation_locations():
    """
    Fetch historical data for all validation locations.
    """
    client = get_cds_client()
    
    print("=" * 70)
    print("Fetching historical data for validation locations")
    print("=" * 70)
    
    results = {}
    for location_name, lat, lon, climate_zone in VALIDATION_LOCATIONS:
        try:
            result_file = fetch_location_data(
                client, location_name, lat, lon, HISTORICAL_START_YEAR, HISTORICAL_END_YEAR
            )
            results[location_name] = {
                "files": result_file,
                "lat": lat,
                "lon": lon,
                "climate_zone": climate_zone,
            }
        except Exception as e:
            print(f"✗ Failed to fetch {location_name}: {e}")
            continue
    
    print("\n" + "=" * 70)
    print(f"Fetched data for {len(results)}/{len(VALIDATION_LOCATIONS)} locations")
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    fetch_all_validation_locations()
