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
    ("Zurich, Switzerland", 47.3769, 8.5417, "alpine"),
    ("Munich, Germany", 48.1351, 11.5820, "continental"),
    ("Cologne, Germany", 50.9375, 6.9603, "temperate"),
    ("Frankfurt, Germany", 50.1109, 8.6821, "temperate"),
    ("Hamburg, Germany", 53.5511, 9.9937, "maritime"),
    ("Gothenburg, Sweden", 57.7089, 11.9746, "maritime"),
    ("Malmo, Sweden", 55.6050, 13.0038, "temperate"),
]

# Time period for validation
# Start with 2020 only to test CDS access, then expand once working
BASELINE_START_YEAR = 2020
BASELINE_END_YEAR = 2020
HISTORICAL_START_YEAR = 2020
HISTORICAL_END_YEAR = 2020

# SI-x base temperature, as used by USA-NPN (usa-npn/gridded_models,
# compute_prism_six.py BASE_TEMP). The model runs in Fahrenheit.
SI_X_BASE_TEMP_F = 31

# Reference data sources (for documentation)
REFERENCE_SOURCES = {
    "DWD": "opendata.dwd.de (German Weather Service phenology data)",
    "Nature's Calendar": "www.naturescalendar.org.uk (Woodland Trust, UK)",
    "PEP725": "pep725.eu (visual/spot-check only, not for bulk download)",
    "Horticultural": "Public gardening/horticultural sources",
}
