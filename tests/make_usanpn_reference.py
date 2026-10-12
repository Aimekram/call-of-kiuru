#!/usr/bin/env python3
"""
Compute reference SI-x outputs with USA-NPN's own code, for the test in
test_si_x_matches_usanpn.py.

USA-NPN's repository (github.com/usa-npn/gridded_models) has no licence, so
none of its code is kept here. This script downloads the two files that hold
the model, at a pinned commit, checks them against pinned SHA-256 hashes, and
runs spring_index(), the function USA-NPN's map scripts call
(compute_prism_six.py, spring_index/postgis_driver.py), the way they call
it: daily Tmax/Tmin in °F, base temperature 31 °F, days 1-240, each plant's
leaf model first and its result passed to the bloom model.

The same file holds two other entry points that are not used here:
spring_index_for_point(), which USA-NPN's QC script uses and which skips the
day-to-day temperature adjustment, and spring_index_hourly(), which takes
hourly temperatures.

Only the resulting days of year are saved, to tests/fixtures/. Needs network
access. The ERA5 reference is written only if the ERA5 downloads are present.

Usage:
    python -m tests.make_usanpn_reference
"""

import datetime
import hashlib
import importlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

from tests import si_x_cases

REPO = "usa-npn/gridded_models"
COMMIT = "25b3ac6f38da89a3c32ecb5f39da7244300ae159"
FILES = {
    "spring_index/spring_index.py":
        "71468c44c7be03fc9694500da085c4ae33f5e80809282cf984bee06c60e37e5b",
    "spring_index/solar_declination.py":
        "214d0466aa094a534af141bf9674b4a7c6ee3c1c8a93a193831b28b9f193a5a4",
}
BASE_TEMP_F = 31

FIXTURES = Path(__file__).parent / "fixtures"


def load_usanpn_model(directory):
    """Download the pinned files, verify them, and import spring_index()."""
    for path, expected in FILES.items():
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{path}"
        content = urllib.request.urlopen(url, timeout=60).read()
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            raise SystemExit(f"{path}: hash {actual} does not match the pinned one")
        target = Path(directory) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    sys.path.insert(0, str(directory))
    module = importlib.import_module("spring_index.spring_index")
    if Path(directory).resolve() not in Path(module.__file__).resolve().parents:
        raise SystemExit(f"spring_index was imported from {module.__file__}, "
                         "not from the verified download")
    return module.spring_index


def run_usanpn(spring_index, lats, tmax_c, tmin_c, dtype=np.float64):
    """
    USA-NPN leaf and bloom day for each case and plant, as
    [[leaf x 3 plants, bloom x 3 plants], ...] with None where not reached.

    Cases are stacked as grid rows (one "latitude" each, one column). As in
    USA-NPN's scripts, the same temperature arrays are passed to every call;
    spring_index() adjusts them in place.
    """
    max_f = (np.array(tmax_c, dtype=dtype) * 1.8 + 32)[:, np.newaxis, :]
    min_f = (np.array(tmin_c, dtype=dtype) * 1.8 + 32)[:, np.newaxis, :]
    lats = np.array(lats, dtype=float)

    leaf, bloom = {}, {}
    for plant in si_x_cases.PLANTS:
        leaf[plant] = spring_index(max_f, min_f, BASE_TEMP_F, None, "leaf", plant, lats)
        bloom[plant] = spring_index(max_f, min_f, BASE_TEMP_F, leaf[plant], "bloom", plant, lats)

    def day(value):
        return None if value < 0 else int(value)

    return [[day(leaf[p][i, 0]) for p in si_x_cases.PLANTS]
            + [day(bloom[p][i, 0]) for p in si_x_cases.PLANTS]
            for i in range(len(lats))]


def header():
    return {
        "source": {"repo": REPO, "commit": COMMIT, "files": FILES},
        "generated": datetime.date.today().isoformat(),
        "base_temp_f": BASE_TEMP_F,
        "n_days": si_x_cases.N_DAYS,
        "columns": [f"{event}_{plant}" for event in ("leaf", "bloom")
                    for plant in si_x_cases.PLANTS],
    }


def write(name, content):
    path = FIXTURES / name
    path.write_text(json.dumps(content, separators=(",", ":")) + "\n")
    print(f"✓ Wrote {path}")


def differing(a, b):
    return sum(x != y for row_a, row_b in zip(a, b) for x, y in zip(row_a, row_b))


def main():
    with tempfile.TemporaryDirectory() as directory:
        spring_index = load_usanpn_model(directory)

        cases = si_x_cases.synthetic_cases()
        lats, tmax, tmin = zip(*cases)
        outputs = run_usanpn(spring_index, lats, tmax, tmin)
        # Production reads its rasters as 32-bit floats; record whether that
        # changes any day.
        as_float32 = run_usanpn(spring_index, lats, tmax, tmin, dtype=np.float32)
        write("usanpn_synthetic.json", {
            **header(),
            "inputs_sha256": si_x_cases.synthetic_checksum(cases),
            "days_changed_by_float32_inputs": differing(outputs, as_float32),
            "cases": outputs,
        })
        print(f"  {len(cases)} synthetic cases; 32-bit inputs change "
              f"{differing(outputs, as_float32)} of {6 * len(cases)} days")

        cities = {}
        for location, lat, lon in si_x_cases.era5_locations():
            daily = si_x_cases.era5_daily(location, lat, lon)
            if daily is None:
                print(f"  {location}: no ERA5 download, skipped")
                continue
            years = si_x_cases.era5_years(daily)
            n = si_x_cases.N_DAYS
            tmax = [years[y][0][:n] for y in years]
            tmin = [years[y][1][:n] for y in years]
            outputs = run_usanpn(spring_index, [lat] * len(years), tmax, tmin)
            cities[location] = {
                "inputs_sha256": si_x_cases.checksum(*[v for y in years for v in years[y]]),
                "years": dict(zip(map(str, years), outputs)),
            }
        if cities:
            write("usanpn_era5.json", {
                **header(),
                "era5_years": [si_x_cases.ERA5_FIRST_YEAR, si_x_cases.ERA5_LAST_YEAR],
                "cities": cities,
            })
            print(f"  {sum(len(c['years']) for c in cities.values())} ERA5 city-years")


if __name__ == "__main__":
    main()
