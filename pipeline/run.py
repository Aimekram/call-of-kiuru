#!/usr/bin/env python3
"""
Build data/bloom.json: for every city in pipeline/locations.json, the
modelled spring bloom for each year since 1940, the 1991-2020 average,
and how the current year compares.

Past years come from the file itself once it exists; a normal run only
downloads the recent period (the year after the archive up to today) and
recomputes those years. Values are stored as computed, unrounded.

Usage:
    python -m pipeline.run [--rebuild] [--offline]

    --rebuild   recompute every year from the full ERA5 archive
    --offline   use the ERA5 downloads already on disk, request nothing
"""

import argparse
import datetime
import json
import os
from pathlib import Path

from pipeline import bloom, era5
from validation.cds_fetch import get_cds_client
from validation.config import DATA_DIR

LOCATIONS_FILE = Path(__file__).parent / "locations.json"
OUTPUT_FILE = DATA_DIR / "bloom.json"


def load_locations():
    return json.loads(LOCATIONS_FILE.read_text())


def archived_bloom(client, city, previous, rebuild):
    """Bloom day for the archive years: from the existing output, or recomputed."""
    first, last = era5.ARCHIVE_YEARS
    if previous and not rebuild:
        rows = {r["year"]: r["bloom_doy"] for r in previous["rows"]
                if r["city"] == city["slug"] and r["year"] <= last}
        if sorted(rows) == list(range(first, last + 1)):
            return rows
    return bloom.bloom_by_year(era5.archive_daily(client, city), city["lat"])


def build(client, today, previous=None, rebuild=False):
    """The output as a dict. With client None, only downloads on disk are used."""
    cities, rows = [], []
    for city in load_locations():
        if client is not None:
            era5.download_recent(client, city, today)
        entry, city_rows = bloom.city_result(
            city, archived_bloom(client, city, previous, rebuild), era5.recent_daily(city))
        cities.append(entry)
        rows += city_rows

    return {
        "generated": today.isoformat(),
        "data_through": min(c["current"]["data_through"] for c in cities),
        "measure": "SI-x first bloom index (mean of three plant models), day of year",
        "baseline_years": list(bloom.BASELINE_YEARS),
        "attribution": "Contains modified Copernicus Climate Change Service information "
                       f"{today.year}.",
        "cities": cities,
        "rows": rows,
    }


def check_against_previous(result, previous):
    """Refuse an output that has lost ground: older data or fewer rows per
    city than the file it would replace."""
    if not previous:
        return
    before = {c["slug"]: c["current"]["data_through"] for c in previous["cities"]}
    for city in result["cities"]:
        slug, through = city["slug"], city["current"]["data_through"]
        if slug in before and through < before[slug]:
            raise SystemExit(f"{slug}: data through {through}, but the existing file has "
                             f"{before[slug]}. Not written.")
        had = sum(r["city"] == slug for r in previous["rows"])
        has = sum(r["city"] == slug for r in result["rows"])
        if has < had:
            raise SystemExit(f"{slug}: {has} rows, but the existing file has {had}. Not written.")


def write(result):
    """Replace the output in one step, so a failure cannot leave half a file."""
    temporary = OUTPUT_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    os.replace(temporary, OUTPUT_FILE)


def summary(result):
    """One line per city, rounded for reading."""
    lines = []
    for city in result["cities"]:
        current = city["current"]
        if current["status"] == "bloomed":
            # "+ 0.0" turns a rounded -0.0 into 0.0.
            lines.append(f"  {city['name']:11s} {current['year']}: day {current['bloom_doy']:6.2f}, "
                         f"{round(current['days_vs_baseline'], 1) + 0.0:+.1f} days vs "
                         f"{city['baseline_doy']:.1f}")
        else:
            lines.append(f"  {city['name']:11s} {current['year']}: not yet "
                         f"(usual day {city['baseline_doy']:.1f})")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--rebuild", action="store_true",
                        help="recompute every year from the full ERA5 archive")
    parser.add_argument("--offline", action="store_true",
                        help="use the ERA5 downloads already on disk, request nothing")
    args = parser.parse_args()

    previous = json.loads(OUTPUT_FILE.read_text()) if OUTPUT_FILE.exists() else None
    today = datetime.datetime.now(datetime.timezone.utc).date()
    client = None if args.offline else get_cds_client()
    result = build(client, today, previous, args.rebuild)
    check_against_previous(result, previous)
    write(result)

    print(f"✓ Wrote {OUTPUT_FILE} (data through {result['data_through']})")
    print(summary(result))


if __name__ == "__main__":
    main()
