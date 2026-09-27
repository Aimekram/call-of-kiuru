#!/usr/bin/env python3
"""
Call of Kiuru Validation Runner

Main entry point for running the validation workflow:
1. Fetch climate data from Copernicus CDS
2. Run SI-x model predictions
3. Compare against reference data
4. Generate validation report

Usage:
    python run_validation.py [--fetch-only] [--model-only] [--compare]
"""

import sys
import argparse
import pandas as pd
import numpy as np
from pathlib import Path

# Adjust path to import from validation package
sys.path.insert(0, str(Path(__file__).parent))

from validation.config import (
    DATA_DIR,
    RAW_DATA_DIR,
    VALIDATION_LOCATIONS,
    BASELINE_START_YEAR,
    BASELINE_END_YEAR,
)
from validation.cds_fetch import fetch_all_validation_locations
from validation.si_x_model import SIxModel
from validation.validator import ValidationLog


def parse_grib_to_dataframe(grib_files, location_name):
    """
    Parse GRIB file from CDS into daily temperature dataframe.
    
    Note: Requires cfgrib library. Install with: pip install cfgrib
    
    Args:
        grib_file: Path to .grib file
        location_name: Name of location (for logging)
    
    Returns:
        DataFrame with columns: date, tmax_c, tmin_c
    """
    try:
        import cfgrib
    except ImportError:
        print("ERROR: cfgrib required to parse GRIB files.")
        print("Install with: pip install cfgrib")
        raise
    
    print(f"  Parsing GRIB files: {grib_files['maximum']}, {grib_files['minimum']}")
    
    try:
        ds_tmax = cfgrib.open_file(str(grib_files["maximum"]))
        ds_tmin = cfgrib.open_file(str(grib_files["minimum"]))
        
        # Extract time series for the nearest grid point
        tmax = ds_tmax['2t'].values - 273.15  # Convert from Kelvin to Celsius
        tmin = ds_tmin['2t'].values - 273.15
        times = ds_tmax['time'].values
        
        df = pd.DataFrame({
            'date': pd.to_datetime(times),
            'tmax_c': tmax,
            'tmin_c': tmin,
        })
        
        return df.sort_values('date').reset_index(drop=True)
    
    except Exception as e:
        print(f"  ERROR parsing {grib_files}: {e}")
        raise


def run_model_on_location(model, temperatures_df):
    """
    Run SI-x model on a location's temperature data.
    
    Args:
        model: SIxModel instance
        temperatures_df: DataFrame with columns: date, tmax_c, tmin_c
    """
    print(f"  Running SI-x model for {model.location_name}...")
    
    # Group by year
    temperatures_df['year'] = temperatures_df['date'].dt.year
    temperatures_df['doy'] = temperatures_df['date'].dt.dayofyear
    
    for year, year_data in temperatures_df.groupby('year'):
        year_data = year_data.sort_values('doy')
        
        # Create a 366-day array (pad with NaN for missing days)
        tmax_array = np.full(366, np.nan)
        tmin_array = np.full(366, np.nan)
        
        for _, row in year_data.iterrows():
            doy = int(row['doy'])
            if 1 <= doy <= 366:
                tmax_array[doy - 1] = row['tmax_c']
                tmin_array[doy - 1] = row['tmin_c']
        
        model.add_year_data(year, tmax_array, tmin_array)
    
    # Run predictions
    model.predict_all_years()
    model.compute_baseline_and_anomalies(BASELINE_START_YEAR, BASELINE_END_YEAR)
    
    print(f"  ✓ Predictions for {len(model.leaf_out_doys)} years")
    if model.baseline_doy:
        print(f"    Baseline (1991-2020): DOY {model.baseline_doy:.0f}")


def main():
    parser = argparse.ArgumentParser(description="Call of Kiuru validation workflow")
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch CDS data, don't run model"
    )
    parser.add_argument(
        "--model-only",
        action="store_true",
        help="Only run model (assumes data already fetched)"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare model predictions against reference data (manual step)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("SPRING WATCH — VALIDATION PHASE")
    print("=" * 70 + "\n")
    
    # Step 1: Fetch CDS data
    if not args.model_only:
        print("STEP 1: Fetching CDS climate data")
        print("-" * 70)
        try:
            fetch_results = fetch_all_validation_locations()
            if not fetch_results:
                print("No data fetched. Exiting.")
                return
        except Exception as e:
            print(f"ERROR during data fetch: {e}")
            sys.exit(1)
        
        if args.fetch_only:
            print("\n✓ Data fetch complete. Use --model-only to run predictions.")
            return
    else:
        # Load existing results
        fetch_results = {}
        for location_name, lat, lon, climate_zone in VALIDATION_LOCATIONS:
            safe_name = location_name.lower().replace(", ", "_").replace(" ", "_")
            maximum_file = next(RAW_DATA_DIR.glob(f"{safe_name}_*_maximum.grib"), None)
            minimum_file = next(RAW_DATA_DIR.glob(f"{safe_name}_*_minimum.grib"), None)
            if maximum_file and minimum_file:
                fetch_results[location_name] = {
                    "files": {"maximum": maximum_file, "minimum": minimum_file},
                    "lat": lat,
                    "lon": lon,
                    "climate_zone": climate_zone,
                }
    
    # Step 2: Run SI-x model
    print("\n" + "=" * 70)
    print("STEP 2: Running SI-x phenology model")
    print("-" * 70)
    
    models = {}
    model_results = []
    
    for location_name, result_info in fetch_results.items():
        print(f"\nProcessing {location_name}...")
        
        # Parse GRIB file
        try:
            temps_df = parse_grib_to_dataframe(result_info['files'], location_name)
        except Exception as e:
            print(f"  ✗ Failed to parse GRIB: {e}")
            continue
        
        # Create and run model
        model = SIxModel(
            location_name,
            result_info['lat'],
            result_info['lon'],
            result_info['climate_zone']
        )
        
        try:
            run_model_on_location(model, temps_df)
            models[location_name] = model
            
            # Collect results
            for year, doy in model.leaf_out_doys.items():
                anomaly = model.anomalies.get(year) if hasattr(model, 'anomalies') else None
                model_results.append({
                    'location': location_name,
                    'lat': model.lat,
                    'lon': model.lon,
                    'climate_zone': model.climate_zone,
                    'year': year,
                    'leaf_out_doy': doy,
                    'baseline_doy': model.baseline_doy,
                    'anomaly_days': anomaly,
                })
        
        except Exception as e:
            print(f"  ✗ Model error: {e}")
            continue
    
    # Save model results
    if model_results:
        results_df = pd.DataFrame(model_results)
        results_file = DATA_DIR / "model_predictions.csv"
        results_df.to_csv(results_file, index=False)
        print(f"\n✓ Saved {len(model_results)} model predictions to {results_file}")
        
        # Print summary by location
        print("\nModel Summary by Location:")
        print("-" * 70)
        for location_name, model in models.items():
            print(f"{location_name} ({model.climate_zone}):")
            print(f"  Baseline (1991-2020): DOY {model.baseline_doy:.0f if model.baseline_doy else 'N/A'}")
            valid_years = [y for y, doy in model.leaf_out_doys.items() if doy is not None]
            print(f"  Years with predictions: {len(valid_years)}")
    
    # Step 3: Manual validation comparison
    print("\n" + "=" * 70)
    print("STEP 3: Validation against reference data (manual)")
    print("-" * 70)
    print("""
Next steps:
1. Obtain reference leaf-out dates for the locations above from:
   - DWD (Germany): opendata.dwd.de
   - Nature's Calendar (UK): naturescalendar.org.uk
   - PEP725 (visual spot-check): pep725.eu
   - Horticultural/gardening sources

2. Create a CSV file: data/reference_observations.csv
   With columns: location, year, leaf_out_doy, source, notes

3. Run this script again with --compare flag to validate.

For now, model predictions are saved in: {results_file}
    """)
    
    if args.compare:
        print("Validation comparison mode (implement with reference data)")


if __name__ == "__main__":
    main()
