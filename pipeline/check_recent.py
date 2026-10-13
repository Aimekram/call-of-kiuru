#!/usr/bin/env python3
"""
Compare the pipeline's output with lilac observations from years after the
validation period (run_bloom_test.py ends in 2024).

Germany only: DWD publishes the current and previous year in its "recent"
file, still subject to revision and, for the current year, incomplete. The
Swedish dataset ends in 2024.

Uses the DWD files already downloaded; delete data/raw/phenology/*_akt.txt
to fetch the latest.

Usage:
    python -m pipeline.check_recent
"""

import json

import numpy as np

from pipeline import era5, run
from validation.reference_fetch import build_bloom_references


def main():
    result = json.loads(run.OUTPUT_FILE.read_text())
    model = {(r["city"], r["year"]): r["bloom_doy"] for r in result["rows"]}
    slug = {city["key"]: city["slug"] for city in run.load_locations()}
    first = era5.ARCHIVE_YEARS[1] + 1
    last = max(year for _city, year in model)

    observed = build_bloom_references(first, last)
    print(f"{'City':11s} {'Year':>4s} {'Observed':>8s} {'Reports':>7s} {'Model':>7s} {'Error':>6s}")
    errors = {}
    for row in observed.sort_values(["year", "location"]).itertuples():
        day = model.get((slug[row.location], row.year))
        if day is None:
            continue
        errors.setdefault(row.year, []).append(day - row.doy)
        print(f"{slug[row.location]:11s} {row.year:4d} {row.doy:8.1f} {row.n_obs:7d} "
              f"{day:7.2f} {day - row.doy:+6.1f}")
    for year, values in errors.items():
        values = np.array(values)
        print(f"{year}: {len(values)} cities, mean error {values.mean():+.1f} days, "
              f"RMSE {np.sqrt((values ** 2).mean()):.1f}")


if __name__ == "__main__":
    main()
