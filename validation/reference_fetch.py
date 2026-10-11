"""
Build lilac (Syringa vulgaris) first-bloom references per (city, year) from
open national phenology data, for comparison with the SI-x bloom index.

- DWD (Germany), CC BY 4.0: annual reporters, wild plants, "Flieder"
  (lilac), phase 5 = beginning of flowering.
- SLU Naturens Kalender (Sweden), CC0: species 8472 (Syringa vulgaris),
  phase 53 = start of flowering (BBCH 61). Only quality = 1 rows, i.e.
  observers in the phenology observer programme, who report by the standard
  protocol (quality = 0: observer unknown or not in the programme; see
  metadata_plants_calendar_2008-2024.pdf in the dataset documentation).

Each reference is the median day of year over all observations near the
city in that year: within 0.5° (lat/lon distance) for DWD's dense network,
1° for SLU's sparse one. This reproduces the hand-built 2020 values exactly
for Berlin, Munich, Stockholm and Gothenburg; the hand-built Cologne,
Frankfurt and Hamburg values used fewer stations (medians differ 0-2 days),
and the hand-built Malmö value included a quality = 0 row (130.5, now 139).
No outlier removal: the median is robust to the odd implausible date.
"""

import numpy as np
import pandas as pd
import requests

from .config import DATA_DIR, VALIDATION_LOCATIONS

PHENOLOGY_DIR = DATA_DIR / "raw" / "phenology"

_DWD_BASE = "https://opendata.dwd.de/climate_environment/CDC"
DWD_LILAC_URL = (f"{_DWD_BASE}/observations_germany/phenology/annual_reporters/wild/"
                 "historical/PH_Jahresmelder_Wildwachsende_Pflanze_Flieder_1925_2024_hist.txt")
# The historical file ends at the last quality-checked year; newer years
# (still subject to revision) are in the "recent" file.
DWD_LILAC_RECENT_URL = (f"{_DWD_BASE}/observations_germany/phenology/annual_reporters/wild/"
                        "recent/PH_Jahresmelder_Wildwachsende_Pflanze_Flieder_akt.txt")
DWD_STATIONS_URL = f"{_DWD_BASE}/help/PH_Beschreibung_Phaenologie_Stationen_Jahresmelder.txt"
SLU_URL = ("https://api.researchdata.se/dataset/2022-86-1/2/file/data/"
           "plants_calendar_2008-2024.csv")

DWD_BLOOM_PHASE = 5
SLU_LILAC_SPECIES = 8472
SLU_BLOOM_PHASE = 53
SLU_PROGRAMME_OBSERVER = 1

# Which network covers which country, and the search box half-width in degrees.
NETWORKS = {"Germany": ("DWD", 0.5), "Sweden": ("SLU", 1.0)}


def _download(url):
    path = PHENOLOGY_DIR / url.rsplit("/", 1)[-1]
    if not path.exists():
        PHENOLOGY_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  Downloading {url}")
        response = requests.get(url, timeout=300)
        response.raise_for_status()
        path.write_bytes(response.content)
    return path


def _read_dwd_semicolon(path):
    df = pd.read_csv(path, sep=";", encoding="latin-1", skipinitialspace=True, dtype=str)
    df.columns = df.columns.str.strip()
    return df.apply(lambda col: col.str.strip())


def load_dwd_bloom():
    """DWD lilac phase-5 observations: year, doy, lat, lon."""
    historical = _read_dwd_semicolon(_download(DWD_LILAC_URL))
    recent = _read_dwd_semicolon(_download(DWD_LILAC_RECENT_URL))
    recent = recent[~recent["Referenzjahr"].isin(historical["Referenzjahr"])]
    obs = pd.concat([historical, recent])
    stations = _read_dwd_semicolon(_download(DWD_STATIONS_URL))

    obs = obs[obs["Phase_id"].astype(int) == DWD_BLOOM_PHASE]
    obs = obs.assign(station=obs["Stations_id"].astype(int),
                     year=obs["Referenzjahr"].astype(int),
                     doy=obs["Jultag"].astype(int))
    stations = stations.assign(station=stations["Stations_id"].astype(int),
                               lat=stations["geograph.Breite"].astype(float),
                               lon=stations["geograph.Laenge"].astype(float))
    return obs.merge(stations[["station", "lat", "lon"]], on="station")[
        ["year", "doy", "lat", "lon"]]


def load_slu_bloom():
    """SLU lilac phase-53 observations by programme observers: year, doy, lat, lon."""
    df = pd.read_csv(_download(SLU_URL), low_memory=False)
    df = df[(df["species_id"] == SLU_LILAC_SPECIES) & (df["phase_id"] == SLU_BLOOM_PHASE)
            & (df["quality"] == SLU_PROGRAMME_OBSERVER)]
    return df.rename(columns={"obs_year": "year", "obs_doy": "doy",
                              "latitude": "lat", "longitude": "lon"})[
        ["year", "doy", "lat", "lon"]]


def build_bloom_references(start_year, end_year):
    """One row per (city, year) with at least one nearby observation."""
    observations = {"DWD": load_dwd_bloom(), "SLU": load_slu_bloom()}
    licenses = {"DWD": "CC BY 4.0", "SLU": "CC0"}

    rows = []
    for location, lat, lon, _zone in VALIDATION_LOCATIONS:
        country = location.split(", ")[-1]
        if country not in NETWORKS:
            continue
        source, radius = NETWORKS[country]
        obs = observations[source]
        distance = np.hypot(obs["lat"] - lat, obs["lon"] - lon)
        near = obs[obs["year"].between(start_year, end_year) & (distance <= radius)]
        for year, group in near.groupby("year"):
            rows.append({
                "location": location,
                "year": year,
                "event": "bloom",
                "species": "Syringa vulgaris",
                "doy": group["doy"].median(),
                "n_obs": len(group),
                "source": source,
                "notes": (f"Median within {radius} deg, range "
                          f"{group['doy'].min()}-{group['doy'].max()}. {licenses[source]}."),
            })
    return pd.DataFrame(rows)
