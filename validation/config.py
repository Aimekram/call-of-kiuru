"""
Configuration for the Call of Kiuru validation phase.
Includes CDS API setup, validation locations, and model parameters.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
VALIDATION_LOG_FILE = BASE_DIR / "VALIDATION_LOG.md"

# Create directories if they don't exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Copernicus CDS API
CDS_API_URL = "https://cds.climate.copernicus.eu/api/v2"
# Set CDS_API_KEY in your environment or .env file
# It will be read as: os.getenv("CDS_API_KEY")
# For testing: cdsapi will check ~/.cdsapirc first

# Validation locations: (name, lat, lon, climate_zone)
VALIDATION_LOCATIONS = [
    ("Berlin, Germany", 52.52, 13.41, "continental"),
    ("Valencia, Spain", 39.47, -0.38, "mediterranean"),
    ("Edinburgh, Scotland", 55.95, -3.19, "maritime"),
    ("Stockholm, Sweden", 59.33, 18.07, "nordic"),
    ("Prague, Czechia", 50.08, 14.44, "continental"),
    ("Lyon, France", 45.76, 4.84, "temperate"),
]

# Time period for validation
# Start with 2020 only to test CDS access, then expand once working
BASELINE_START_YEAR = 2020
BASELINE_END_YEAR = 2020
HISTORICAL_START_YEAR = 2020
HISTORICAL_END_YEAR = 2020

# SI-x Model Parameters
# Growing-degree-day model thresholds and weights
SI_X_BASE_TEMP = 10.0  # °C, temperature below which GDD = 0
SI_X_MIN_TEMP = -17.0  # °C, min temp cutoff
SI_X_MAX_TEMP = 30.0   # °C, max temp cutoff
SI_X_SPRING_START_DOY = 59  # Day of year (Feb 28/29) when SI-x accumulation starts

# European research suggests daytime (max) temp is more predictive than mean
# Weighting: proportion of max temp vs. mean temp in GDD calculation
SI_X_MAX_TEMP_WEIGHT = 0.7  # 70% max, 30% mean
SI_X_MEAN_TEMP_WEIGHT = 0.3

# Growing-degree-day accumulation threshold for leaf-out
# (varies by species/cultivar, this is a reasonable European default)
SI_X_GDD_THRESHOLD = 130.0  # Growing degree days

# Reference data sources (for documentation)
REFERENCE_SOURCES = {
    "DWD": "opendata.dwd.de (German Weather Service phenology data)",
    "Nature's Calendar": "www.naturescalendar.org.uk (Woodland Trust, UK)",
    "PEP725": "pep725.eu (visual/spot-check only, not for bulk download)",
    "Horticultural": "Public gardening/horticultural sources",
}
