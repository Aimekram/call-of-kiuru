"""
The pipeline's output, data/bloom.json, must be what the validated model
gives, its arithmetic must hold exactly, and the pipeline must behave at the
awkward moments: before bloom, at the turn of the year, and when the newest
data is incomplete.

Run from the repository root:
    python -m unittest -v tests.test_pipeline

Needs no downloads: it reads the committed output and the USA-NPN reference,
and builds its own temperature series for the scenarios.
"""

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import bloom, era5, run
from tests import si_x_cases
from validation.config import VALIDATION_LOCATIONS
from validation.reference_fetch import NETWORKS

FIXTURES = Path(__file__).parent / "fixtures"


def usanpn_bloom(days):
    """The index from one reference row: the mean of the three bloom days."""
    return float(np.mean(days[3:]))


class Locations(unittest.TestCase):

    def test_cities_are_the_validated_ones(self):
        """Same names and coordinates as the validation, lilac network required."""
        validated = {name: (lat, lon) for name, lat, lon, _zone in VALIDATION_LOCATIONS
                     if name.split(", ")[-1] in NETWORKS}
        cities = run.load_locations()
        self.assertEqual({c["key"]: (c["lat"], c["lon"]) for c in cities}, validated)
        self.assertEqual(len({c["slug"] for c in cities}), len(cities))
        for city in cities:
            self.assertEqual(city["key"].split(", ")[-1], city["country"])


class Output(unittest.TestCase):
    """The committed data/bloom.json. Every comparison is exact: the file
    holds unrounded values."""

    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(run.OUTPUT_FILE.read_text())
        cls.reference = json.loads((FIXTURES / "usanpn_era5.json").read_text())["cities"]
        cls.by_city = {}
        for row in cls.result["rows"]:
            cls.by_city.setdefault(row["city"], {})[row["year"]] = row

    def test_archive_years_match_usanpn_reference(self):
        """Every archived city-year equals the mean of USA-NPN's three bloom days."""
        compared = 0
        for city in run.load_locations():
            for year, days in self.reference[city["key"]]["years"].items():
                self.assertEqual(self.by_city[city["slug"]][int(year)]["bloom_doy"],
                                 usanpn_bloom(days), f"{city['key']} {year}")
                compared += 1
        self.assertEqual(compared, 680)

    def test_no_year_missing_or_repeated(self):
        first = era5.ARCHIVE_YEARS[0]
        for city in self.result["cities"]:
            years = [r["year"] for r in self.result["rows"] if r["city"] == city["slug"]]
            self.assertEqual(years, list(range(first, first + len(years))), city["slug"])
            self.assertGreaterEqual(years[-1], era5.ARCHIVE_YEARS[1], city["slug"])

    def test_baseline_and_differences(self):
        self.assertEqual(bloom.BASELINE_YEARS, (1991, 2020))
        self.assertEqual(self.result["baseline_years"], [1991, 2020])
        first, last = bloom.BASELINE_YEARS
        for city in self.result["cities"]:
            rows = self.by_city[city["slug"]]
            days = [rows[year]["bloom_doy"] for year in range(first, last + 1)]
            self.assertEqual(city["baseline_doy"], sum(days) / len(days), city["slug"])
            for row in rows.values():
                self.assertEqual(row["days_vs_baseline"],
                                 row["bloom_doy"] - city["baseline_doy"], row)

    def test_current_year(self):
        for city in self.result["cities"]:
            current, rows = city["current"], self.by_city[city["slug"]]
            self.assertIn(current["status"], ("bloomed", "not_yet"))
            if current["status"] == "bloomed":
                self.assertEqual(current["bloom_doy"], rows[current["year"]]["bloom_doy"])
                self.assertEqual(current["days_vs_baseline"],
                                 rows[current["year"]]["days_vs_baseline"])
            else:
                self.assertNotIn(current["year"], rows)
                self.assertNotIn("bloom_doy", current)
            self.assertLessEqual(self.result["data_through"], current["data_through"])

    def test_past_years_are_reused_exactly(self):
        """A normal run reads archived years from the file, asking for no
        download, and gets exactly the values a rebuild computes."""
        first, last = era5.ARCHIVE_YEARS
        for city in run.load_locations():
            reused = run.archived_bloom(None, city, self.result, rebuild=False)
            self.assertEqual(sorted(reused), list(range(first, last + 1)))
            for year, days in self.reference[city["key"]]["years"].items():
                self.assertEqual(reused[int(year)], usanpn_bloom(days), f"{city['key']} {year}")

    def test_summary_rounds_only_for_display(self):
        before = json.dumps(self.result, sort_keys=True)
        text = run.summary(self.result)
        self.assertEqual(json.dumps(self.result, sort_keys=True), before)
        self.assertNotIn("-0.0 ", text)


def hourly(start, hours, value=280.0):
    times = pd.date_range(start, periods=hours, freq="h")
    return pd.DataFrame({"valid_time": times, "t2m": value})


class UsableDays(unittest.TestCase):
    """What counts as data: complete days, in an unbroken run from RECENT_START."""

    START = pd.Timestamp(era5.RECENT_START)

    def test_partial_last_day_is_dropped(self):
        days = era5.usable_days(hourly(self.START, 2 * 24 + 7))
        self.assertEqual(list(days["date"]), [self.START, self.START + pd.Timedelta(days=1)])

    def test_last_day_of_empty_values_is_dropped(self):
        data = hourly(self.START, 5 * 24)
        data.loc[data["valid_time"] >= self.START + pd.Timedelta(days=4), "t2m"] = np.nan
        self.assertEqual(len(era5.usable_days(data)), 4)

    def test_a_hole_ends_the_series(self):
        data = hourly(self.START, 5 * 24)
        data.loc[data["valid_time"] == self.START + pd.Timedelta(days=2, hours=7), "t2m"] = np.nan
        self.assertEqual(len(era5.usable_days(data)), 2)

    def test_values_are_daily_extremes_in_celsius(self):
        data = hourly(self.START, 48)
        data["t2m"] = 273.15 + np.arange(48)
        days = era5.usable_days(data)
        self.assertAlmostEqual(days["tmin_c"].iloc[1], 24.0)
        self.assertAlmostEqual(days["tmax_c"].iloc[1], 47.0)

    def test_duplicate_hours_are_refused(self):
        data = hourly(self.START, 48)
        with self.assertRaises(ValueError):
            era5.usable_days(pd.concat([data, data.iloc[[5]]]))

    def test_data_not_starting_on_the_first_day_is_refused(self):
        with self.assertRaises(ValueError):
            era5.usable_days(hourly(self.START + pd.Timedelta(days=1), 72))
        with self.assertRaises(ValueError):
            era5.usable_days(hourly(self.START, 23))


class CityResult(unittest.TestCase):
    """bloom.city_result at the awkward moments, on built series: the year
    after the archive is complete, the next year is cut wherever a scenario
    needs."""

    @classmethod
    def setUpClass(cls):
        reference = json.loads((FIXTURES / "usanpn_synthetic.json").read_text())["cases"]
        cases = si_x_cases.synthetic_cases()
        blooming = [i for i, days in enumerate(reference) if None not in days]
        first, second = blooming[0], blooming[1]
        cls.lat = cases[first][0]
        cls.first_year_bloom = usanpn_bloom(reference[first])
        # The second year uses the first series' latitude, so its bloom days
        # come from the model itself, checked against USA-NPN elsewhere.
        cls.year1 = cls.padded(cases[first][1], cases[first][2], 365)
        cls.year2 = cls.padded(cases[second][1], cases[second][2], 365)
        cls.city = {"slug": "test", "name": "Test", "country": "Nowhere",
                    "lat": cls.lat, "lon": 0.0}
        archive_first, archive_last = era5.ARCHIVE_YEARS
        cls.archived = {year: 100.0 + year % 7 for year in range(archive_first, archive_last + 1)}

        full = cls.recent(365)
        cls.plant_days = bloom.predict_spring_index(
            full["tmax_c"].to_numpy()[365:], full["tmin_c"].to_numpy()[365:], cls.lat)["bloom"]

    @staticmethod
    def padded(tmax, tmin, n_days):
        """A series extended with mild days to n_days."""
        extra = n_days - len(tmax)
        return (np.concatenate([tmax, np.full(extra, 15.0)]),
                np.concatenate([tmin, np.full(extra, 5.0)]))

    @classmethod
    def recent(cls, days_of_year2):
        """Daily data: all of the first recent year, then days_of_year2 days."""
        n = 365 + days_of_year2
        return pd.DataFrame({
            "date": pd.date_range(era5.RECENT_START, periods=n),
            "tmax_c": np.concatenate([cls.year1[0], cls.year2[0]])[:n],
            "tmin_c": np.concatenate([cls.year1[1], cls.year2[1]])[:n],
        })

    def result(self, days_of_year2):
        return bloom.city_result(self.city, dict(self.archived), self.recent(days_of_year2))

    def test_first_recent_year_matches_reference(self):
        _entry, rows = self.result(0)
        self.assertEqual(rows[-1]["year"], era5.RECENT_START.year)
        self.assertEqual(rows[-1]["bloom_doy"], self.first_year_bloom)

    def test_at_the_end_of_a_year_that_year_is_current(self):
        entry, rows = self.result(0)
        year = era5.RECENT_START.year
        self.assertEqual(entry["current"]["year"], year)
        self.assertEqual(entry["current"]["status"], "bloomed")
        self.assertEqual(entry["current"]["data_through"], f"{year}-12-31")
        self.assertEqual(len(rows), len(self.archived) + 1)

    def test_first_days_of_a_new_year(self):
        entry, rows = self.result(3)
        year = era5.RECENT_START.year + 1
        self.assertEqual(entry["current"],
                         {"year": year, "status": "not_yet", "data_through": f"{year}-01-03"})
        self.assertEqual(rows[-1]["year"], year - 1)

    def test_not_yet_until_the_last_plant_blooms(self):
        last_plant = max(self.plant_days[p] for p in si_x_cases.PLANTS)
        entry, rows = self.result(last_plant - 1)
        self.assertEqual(entry["current"]["status"], "not_yet")
        self.assertNotIn("bloom_doy", entry["current"])
        self.assertEqual(rows[-1]["year"], era5.RECENT_START.year)

        entry, rows = self.result(last_plant)
        self.assertEqual(entry["current"]["status"], "bloomed")
        self.assertEqual(entry["current"]["bloom_doy"], self.plant_days["average"])
        self.assertEqual(rows[-1]["bloom_doy"], self.plant_days["average"])

    def test_a_bloom_day_does_not_change_as_more_days_arrive(self):
        last_plant = max(self.plant_days[p] for p in si_x_cases.PLANTS)
        on_the_day = self.result(last_plant)[0]["current"]
        later = self.result(300)[0]["current"]
        self.assertEqual(on_the_day["bloom_doy"], later["bloom_doy"])
        self.assertEqual(on_the_day["days_vs_baseline"], later["days_vs_baseline"])

    def test_baseline_and_difference_are_exact(self):
        entry, rows = self.result(300)
        first, last = bloom.BASELINE_YEARS
        days = [self.archived[year] for year in range(first, last + 1)]
        self.assertEqual(entry["baseline_doy"], sum(days) / len(days))
        for row in rows:
            self.assertEqual(row["days_vs_baseline"], row["bloom_doy"] - entry["baseline_doy"])

    def test_refuses_overlapping_years_and_missing_baseline(self):
        overlapping = {**self.archived, era5.RECENT_START.year: 100.0}
        with self.assertRaises(ValueError):
            bloom.city_result(self.city, overlapping, self.recent(10))
        incomplete = {y: d for y, d in self.archived.items() if y != 2000}
        with self.assertRaises(ValueError):
            bloom.city_result(self.city, incomplete, self.recent(10))

    def test_gap_in_daily_data_is_refused(self):
        holed = self.recent(100).drop(index=40)
        with self.assertRaises(ValueError):
            bloom.city_result(self.city, dict(self.archived), holed)


class Safeguards(unittest.TestCase):

    def test_refuses_to_replace_newer_output(self):
        previous = json.loads(run.OUTPUT_FILE.read_text())
        run.check_against_previous(previous, previous)

        older = json.loads(json.dumps(previous))
        older["cities"][0]["current"]["data_through"] = "2000-01-01"
        with self.assertRaises(SystemExit):
            run.check_against_previous(older, previous)

        fewer = json.loads(json.dumps(previous))
        fewer["rows"] = fewer["rows"][1:]
        with self.assertRaises(SystemExit):
            run.check_against_previous(fewer, previous)


if __name__ == "__main__":
    unittest.main()
