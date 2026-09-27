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
        Path to downloaded file
    """
    # Safe filename
    safe_name = location_name.lower().replace(", ", "_").replace(" ", "_")
    output_files = {
        "maximum": RAW_DATA_DIR / f"{safe_name}_{start_year}-{end_year}_maximum.grib",
        "minimum": RAW_DATA_DIR / f"{safe_name}_{start_year}-{end_year}_minimum.grib",
    }
    
    print(f"\nFetching data for {location_name} ({lat}, {lon})")
    print(f"Period: {start_year}-{end_year} (spring months: Feb-May only)")
    print(f"Outputs: {output_files['maximum']}, {output_files['minimum']}")
    
    # Request only spring months (Feb=02 to May=05) with valid days
    # This reduces CDS cost significantly while preserving full winter-to-spring data for model
    try:
        for statistic, output_file in output_files.items():
            request = {
                "product_type": "daily_statistics",
                "variable": "2m_temperature",
                "year": [str(y) for y in range(start_year, end_year + 1)],
                "month": ["02", "03", "04", "05"],
                "day": [str(d).zfill(2) for d in range(1, 32)],
                "daily_statistic": f"daily_{statistic}",
                "frequency": "1_hourly",
                "time_zone": "UTC+00:00",
                # CDS area order is north, west, south, east. Keep the request local.
                "area": [lat + 0.25, lon - 0.25, lat - 0.25, lon + 0.25],
                "grid": [0.25, 0.25],
                "data_format": "grib",
            }
            print(f"  Fetching daily {statistic}...")
            client.retrieve("derived-era5-single-levels-daily-statistics", request, str(output_file))
            print(f"  ✓ Downloaded to {output_file}")
        return output_files
    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        raise


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
