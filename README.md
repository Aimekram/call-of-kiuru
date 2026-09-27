# Call of Kiuru — Validation Phase

European phenology dashboard validation: testing the SI-x model predictions against real reference data before building the full pipeline.

## Quick Start

### 1. Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install optional GRIB parser (for CDS data)
pip install cfgrib
```

### 2. Configure CDS API

You've already registered at Copernicus CDS. Now configure the API:

**Option A: Using `~/.cdsapirc` (recommended)**

Create `~/.cdsapirc` with:

```
url: https://cds.climate.copernicus.eu/api/v2
key: <YOUR_CDS_API_KEY>
```

**Option B: Using environment variable**

```bash
export CDS_API_KEY="<YOUR_CDS_API_KEY>"
```

### 3. Fetch climate data

This downloads daily temperature data (1991–2024) for all validation locations from Copernicus ERA5:

```bash
python run_validation.py --fetch-only
```

**First run will take 5–15 minutes** (CDS queues requests server-side). Data goes to `data/raw/`.

### 4. Run SI-x model

Once data is fetched, compute leaf-out predictions:

```bash
python run_validation.py --model-only
```

This generates `data/model_predictions.csv` with predicted and baseline leaf-out dates by location and year.

### 5. Validate against reference data

Manually gather reference observations, then compare:

1. Collect observed leaf-out dates from:
   - **DWD** (Germany): [opendata.dwd.de](https://opendata.dwd.de/)
   - **Nature's Calendar** (UK): [naturescalendar.org.uk](https://www.naturescalendar.org.uk/)
   - **PEP725**: [pep725.eu](https://www.pep725.eu/) (visual/spot-check only)
   - **Horticultural sources**: gardening/forestry websites for well-known cities

2. Create `data/reference_observations.csv` with columns:

   ```
   location,year,leaf_out_doy,source,notes
   Berlin Germany,2023,118,DWD,
   Berlin Germany,2022,108,DWD,
   ```

3. Update `validation/validator.py` to load and compare, then run:
   ```bash
   python run_validation.py --compare
   ```

## Project Structure

```
/validation
  ├── __init__.py
  ├── config.py              # Configuration: locations, model params, data paths
  ├── cds_fetch.py           # Copernicus CDS data fetching
  ├── si_x_model.py          # SI-x growing-degree-day phenology model
  └── validator.py           # Compare model predictions vs. reference data
/data
  ├── raw/                   # GRIB files from CDS (auto-created)
  ├── cache/                 # Temporary processing files
  ├── model_predictions.csv  # Model output (auto-generated)
  └── reference_observations.csv  # Your manually-collected reference data
run_validation.py            # Main entry point
requirements.txt             # Python dependencies
PLAN.md                      # Project plan (existing)
```

## The SI-x Model

**Extended Spring Index (SI-x)** predicts leaf-out timing based on accumulated growing degree days (GDD).

Key features:

- **Base temperature**: 10°C (degree days below this don't count)
- **Accumulation start**: Day 59 (Feb 28/29)
- **Threshold**: ~130 GDD (when leaf-out typically occurs)
- **European weighting**: 70% daily max temp, 30% mean (European research shows max more predictive)
- **Physical bounds**: Temperatures clamped to [-17°C, +30°C]

Reference: Schwartz et al. (2013), "Common sense phenology"

## What to Expect

### Model Output

`data/model_predictions.csv`:

```csv
location,lat,lon,climate_zone,year,leaf_out_doy,baseline_doy,anomaly_days
Berlin Germany,52.52,13.41,continental,2020,114,110.0,4.0
Berlin Germany,52.52,13.41,continental,2021,112,110.0,2.0
```

- **leaf_out_doy**: Predicted day-of-year (1–366) for leaf-out
- **baseline_doy**: Median DOY from 1991–2020 reference period
- **anomaly_days**: How many days earlier (negative) or later (positive) than baseline

### Validation Success Criteria

Published European studies report **6.6–8.6 days RMSE**. Target:

- **RMSE < 10 days** overall = proceed to launch
- **Consistent bias** (e.g., "always 5 days early") = apply calibration, proceed
- **Zone-dependent success** (works in some climates, not others) = launch in validated zones only
- **Unreliable everywhere** = revisit model parameters or drop "days" framing in favor of "earlier/typical/later"

## Validation Locations (Default)

| Location            | Climate       | Lat   | Lon   |
| ------------------- | ------------- | ----- | ----- |
| Berlin, Germany     | Continental   | 52.52 | 13.41 |
| Valencia, Spain     | Mediterranean | 39.47 | -0.38 |
| Edinburgh, Scotland | Maritime      | 55.95 | -3.19 |
| Stockholm, Sweden   | Nordic        | 59.33 | 18.07 |
| Prague, Czechia     | Continental   | 50.08 | 14.44 |
| Lyon, France        | Temperate     | 45.76 | 4.84  |

Edit `validation/config.py` to change locations.

## Troubleshooting

### CDS API timeouts

The Copernicus queue can be slow. If a request hangs:

- Wait a few minutes (CDS is busy)
- Cancel (Ctrl+C) and retry later
- Check [CDS status page](https://cds.climate.copernicus.eu/)

### Missing dependencies

```bash
pip install cfgrib eccodes
```

(Some systems need the native `eccodes` library for GRIB parsing)

### No data for a location

Possible reasons:

- Location is outside ERA5 coverage (unlikely for Europe)
- Invalid lat/lon in config
- CDS quota exceeded (free tier is generous; shouldn't happen)

Check `data/raw/` for downloaded files.

## Next Steps After Validation

Once validation succeeds:

1. Document validation results (this becomes public "Methodology" page content)
2. Set up Supabase database (Frankfurt region)
3. Build GitHub Actions workflow for daily pipeline runs
4. Create static site frontend
5. Launch!

See `PLAN.md` section §3 for full validation and §4–8 for the subsequent phases.

## References

- Schwartz, M. D., Ault, T. R., & Pulso, S. L. (2013). "Common sense phenology." _Frontiers in Ecology and Evolution_, 1, 9.
- USA-NPN gridded models: [github.com/usa-npn/gridded_models](https://github.com/usa-npn/gridded_models)
- pyPhenology: [github.com/sdtaylor/pyPhenology](https://github.com/sdtaylor/pyPhenology)
- Copernicus CDS: [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu/)
- DWD open data: [opendata.dwd.de](https://opendata.dwd.de/)
