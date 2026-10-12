"""
Our SI-x implementation must give the same leaf and bloom days as USA-NPN's
code (see make_usanpn_reference.py for how the reference was produced).

Run from the repository root:
    python -m unittest -v tests.test_si_x_matches_usanpn

The synthetic comparison needs only this repository and its requirements.
The ERA5 comparison covers the cities whose ERA5 download is present, and is
skipped if none is.
"""

import json
import unittest
from pathlib import Path

import numpy as np

from tests import si_x_cases
from validation.si_x_model import predict_spring_index

FIXTURES = Path(__file__).parent / "fixtures"


def ours(tmax_c, tmin_c, lat):
    """Our leaf and bloom days in the reference's column order, and the
    two averages."""
    result = predict_spring_index(tmax_c, tmin_c, lat)
    days = [result[event][plant] for event in ("leaf", "bloom")
            for plant in si_x_cases.PLANTS]
    return days, result["leaf"]["average"], result["bloom"]["average"]


class MatchesUsaNpn(unittest.TestCase):

    def check(self, label, days, leaf_average, bloom_average, expected):
        self.assertEqual(days, expected, label)
        # The index is the mean of the three plants, or nothing if any plant
        # has not reached the event.
        for average, plant_days in ((leaf_average, expected[:3]), (bloom_average, expected[3:])):
            if None in plant_days:
                self.assertIsNone(average, label)
            else:
                self.assertAlmostEqual(average, sum(plant_days) / 3, places=9, msg=label)

    def test_synthetic_series(self):
        reference = json.loads((FIXTURES / "usanpn_synthetic.json").read_text())
        cases = si_x_cases.synthetic_cases()
        self.assertEqual(si_x_cases.synthetic_checksum(cases), reference["inputs_sha256"],
                         "synthetic inputs differ from the ones the reference was computed for")
        self.assertEqual(len(cases), len(reference["cases"]))

        for i, ((lat, tmax, tmin), expected) in enumerate(zip(cases, reference["cases"])):
            self.check(f"synthetic case {i} (lat {lat})", *ours(tmax, tmin, lat), expected)

    def test_era5_series(self):
        reference = json.loads((FIXTURES / "usanpn_era5.json").read_text())
        compared = 0
        for location, lat, lon in si_x_cases.era5_locations():
            daily = si_x_cases.era5_daily(location, lat, lon)
            if daily is None:
                continue
            self.assertIn(location, reference["cities"],
                          "ERA5 data present but no reference; rerun make_usanpn_reference")
            city = reference["cities"][location]
            years = si_x_cases.era5_years(daily)
            self.assertEqual(si_x_cases.checksum(*[v for y in years for v in years[y]]),
                             city["inputs_sha256"],
                             f"{location}: ERA5 data differ from the reference's; "
                             "rerun make_usanpn_reference")
            self.assertEqual(sorted(map(str, years)), sorted(city["years"]))
            for year, (tmax, tmin) in years.items():
                # Ours gets the whole year, as in the app; the reference used
                # days 1-240, as USA-NPN's production script does.
                self.check(f"{location} {year}", *ours(tmax, tmin, lat), city["years"][str(year)])
                compared += 1
        if not compared:
            self.skipTest("no ERA5 downloads in data/raw/timeseries/")
        print(f"\n  compared {compared} ERA5 city-years")


if __name__ == "__main__":
    unittest.main()
