"""
The site built from data/bloom.json: the wording and rounding helpers, and
the pages themselves.

Run from the repository root:
    python -m unittest -v tests.test_site

Needs no downloads. The table-sorting check runs if Node.js is installed.
"""

import copy
import datetime
import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from pipeline import build_site, run

VOID = {"meta", "link", "br", "img", "hr", "input"}


class Page(HTMLParser):
    """Collects text, links and attributes, and checks that tags are balanced."""

    def __init__(self, source):
        super().__init__()
        self.open, self.errors, self.links, self.text, self.attributes = [], [], [], [], []
        self.feed(source)
        self.close()
        self.errors += [f"unclosed <{tag}>" for tag in self.open]
        self.plain = " ".join(" ".join(self.text).split())

    def handle_starttag(self, tag, attrs):
        self.attributes.append((tag, dict(attrs)))
        if tag == "a":
            self.links.append(dict(attrs).get("href"))
        if tag not in VOID:
            self.open.append(tag)

    def handle_endtag(self, tag):
        if not self.open or self.open[-1] != tag:
            self.errors.append(f"unexpected </{tag}>")
        else:
            self.open.pop()

    def handle_data(self, data):
        self.text.append(data)


class Wording(unittest.TestCase):

    def test_whole_days(self):
        cases = {0.0: 0, 0.49: 0, 0.5: 1, 1.4: 1, 1.5: 2, 2.5: 3, -0.04: 0, -0.49: 0,
                 -0.5: -1, -1.5: -2, -7.72: -8, 121.67: 122}
        for value, expected in cases.items():
            self.assertEqual(build_site.whole_days(value), expected, value)
        self.assertEqual(str(build_site.whole_days(-0.2)), "0")

    def test_difference_phrase(self):
        self.assertEqual(build_site.difference_phrase(-7.72), "8 days earlier than")
        self.assertEqual(build_site.difference_phrase(-1.2), "1 day earlier than")
        self.assertEqual(build_site.difference_phrase(1.38), "1 day later than")
        self.assertEqual(build_site.difference_phrase(12.5), "13 days later than")
        self.assertEqual(build_site.difference_phrase(-0.4), "the same as")
        self.assertEqual(build_site.difference_phrase(0.3), "the same as")

    def test_signed_days(self):
        self.assertEqual(build_site.signed_days(-7.72), "−8")
        self.assertEqual(build_site.signed_days(1.38), "+1")
        self.assertEqual(build_site.signed_days(-0.04), "0")

    def test_dates(self):
        self.assertEqual(build_site.date_of(1.0, 2026), datetime.date(2026, 1, 1))
        self.assertEqual(build_site.date_of(104.0, 2026), datetime.date(2026, 4, 14))
        # Day 60 is 1 March in an ordinary year and 29 February in a leap year.
        self.assertEqual(build_site.date_of(60.0, 2025), datetime.date(2025, 3, 1))
        self.assertEqual(build_site.date_of(60.0, 2024), datetime.date(2024, 2, 29))
        self.assertEqual(build_site.date_of(121.67, 2026), datetime.date(2026, 5, 2))
        self.assertEqual(build_site.day_month(datetime.date(2026, 5, 2)), "2 May")
        self.assertEqual(build_site.usual_date(111.72), "22 April")


class Built(unittest.TestCase):
    """The site built from the committed data/bloom.json."""

    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(run.OUTPUT_FILE.read_text())
        cls.directory = Path(tempfile.mkdtemp())
        cls.written = build_site.build(cls.result, cls.directory)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory)

    def page(self, path):
        return Page((self.directory / path).read_text())

    def test_one_page_per_city_a_ranking_and_the_method(self):
        expected = {"index.html", "method/index.html"} | {
            f"{c['slug']}/index.html" for c in self.result["cities"]}
        self.assertEqual({str(p.relative_to(self.directory)) for p in self.written}, expected)
        self.assertTrue((self.directory / "static" / "style.css").exists())
        self.assertTrue((self.directory / "static" / "sort.js").exists())

    def test_pages_are_well_formed_and_links_resolve(self):
        for path in self.written:
            page = Page(path.read_text())
            self.assertEqual(page.errors, [], path)
            for link in page.links:
                if link.startswith("https://"):
                    continue
                target = (path.parent / link).resolve()
                self.assertTrue(target.is_dir() or target.exists(), f"{path}: {link}")
                if target.is_dir():
                    self.assertTrue((target / "index.html").exists(), f"{path}: {link}")
            for tag, attributes in page.attributes:
                for name in ("href", "src"):
                    if (tag in ("link", "script") and name in attributes
                            and not attributes[name].startswith("https://")):
                        self.assertTrue((path.parent / attributes[name]).exists(),
                                        f"{path}: {attributes[name]}")

    def test_city_pages_say_what_the_data_says(self):
        for city in self.result["cities"]:
            current = city["current"]
            text = self.page(f"{city['slug']}/index.html").plain
            self.assertIn(f"{city['name']}, {city['country']}", text)
            self.assertIn(f"around {build_site.usual_date(city['baseline_doy'])}", text)
            if current["status"] != "bloomed":
                through = datetime.date.fromisoformat(current["data_through"])
                self.assertIn("The modelled start of spring has not arrived yet in "
                              f"{current['year']}.", text)
                self.assertIn("Temperatures received up to "
                              f"{build_site.day_month(through)} {through.year}", text)
                continue
            phrase = build_site.difference_phrase(current["days_vs_baseline"])
            date = build_site.day_month(build_site.date_of(current["bloom_doy"], current["year"]))
            self.assertIn(f"In {current['year']} the modelled start of spring was {phrase} "
                          "the 1991–2020 average.", text)
            self.assertIn(f"Start of spring {current['year']} {date}", text)

    def test_city_pages_list_every_year(self):
        for city in self.result["cities"]:
            rows = [r for r in self.result["rows"] if r["city"] == city["slug"]]
            source = (self.directory / city["slug"] / "index.html").read_text()
            self.assertEqual(source.count('<th scope="row">'), len(rows), city["slug"])
            for row in rows:
                date = build_site.date_of(row["bloom_doy"], row["year"])
                self.assertIn(f'<th scope="row">{row["year"]}</th>\n'
                              f'<td data-value="{row["bloom_doy"]}">'
                              f'<time datetime="{date.isoformat()}">'
                              f'{build_site.day_month(date)}</time></td>\n'
                              f'<td data-value="{row["days_vs_baseline"]}">'
                              f'{build_site.signed_days(row["days_vs_baseline"])}</td>',
                              source, f"{city['slug']} {row['year']}")

    def test_external_links_open_in_a_new_tab(self):
        external = 0
        for path in self.written:
            for tag, attributes in Page(path.read_text()).attributes:
                if tag != "a":
                    continue
                if attributes["href"].startswith("https://"):
                    external += 1
                    self.assertEqual(attributes.get("target"), "_blank", attributes["href"])
                    self.assertEqual(attributes.get("rel"), "noopener", attributes["href"])
                else:
                    self.assertNotIn("target", attributes, f"{path}: {attributes['href']}")
        self.assertGreater(external, 0)

    def test_method_page_explains_the_average(self):
        source = (self.directory / "method" / "index.html").read_text()
        page = Page(source)
        first, last = self.result["baseline_years"]
        self.assertEqual((first, last), (1991, 2020))
        self.assertIn("For each of the 30 years in 1991–2020", page.plain)
        self.assertIn("The average is the plain mean of those 30 days.", page.plain)
        gaps = []
        for city in self.result["cities"]:
            rows = {r["year"]: r["bloom_doy"] for r in self.result["rows"]
                    if r["city"] == city["slug"]}
            # The average on the page is the mean of the years on the city's page.
            mean = sum(rows[y] for y in range(first, last + 1)) / (last - first + 1)
            self.assertAlmostEqual(mean, city["baseline_doy"], places=9)
            self.assertIn(f'<th scope="row"><a href="../{city["slug"]}/">{city["name"]}</a></th>\n'
                          f'<td>{city["baseline_doy"]:.1f}</td>\n'
                          f'<td>{build_site.usual_date(city["baseline_doy"])}</td>', source)
            gaps.append(sum(rows[y] for y in range(1961, 1991)) / 30 - city["baseline_doy"])
        self.assertIn(f"the 1961–1990 average falls {build_site.whole_days(min(gaps))} to "
                      f"{build_site.whole_days(max(gaps))} days later than the 1991–2020 one",
                      page.plain)
        self.assertGreater(min(gaps), 0)
        self.assertIn("based on data from Deutscher Wetterdienst (CC BY 4.0) and from "
                      "SLU Naturens Kalender (CC0).", page.plain)
        self.assertTrue(any("wmo.int" in link for link in page.links))
        self.assertTrue(any("usanpn.org" in link for link in page.links))

    def test_the_average_links_to_its_explanation(self):
        self.assertIn('<a href="method/">1991–2020 average</a>',
                      (self.directory / "index.html").read_text())
        for city in self.result["cities"]:
            self.assertIn('<dt><a href="../method/">1991–2020 average</a></dt>',
                          (self.directory / city["slug"] / "index.html").read_text())

    def test_ranking_is_ordered_by_the_unrounded_difference(self):
        source = (self.directory / "index.html").read_text()
        bloomed = [c for c in self.result["cities"] if c["current"]["status"] == "bloomed"]
        order = sorted(bloomed, key=lambda c: (c["current"]["days_vs_baseline"], c["name"]))
        positions = [source.index(f'<a href="{c["slug"]}/">') for c in order]
        self.assertEqual(positions, sorted(positions))
        # Cities not yet in bloom come after all the others.
        for city in self.result["cities"]:
            if city not in bloomed:
                self.assertGreater(source.index(f'<a href="{city["slug"]}/">'),
                                   max(positions, default=0))
        for city in order:
            self.assertIn(f'<td data-value="{city["current"]["days_vs_baseline"]}">'
                          f'{build_site.signed_days(city["current"]["days_vs_baseline"])}</td>',
                          source)

    def test_every_page_carries_the_attribution_and_the_caveat(self):
        for path in self.written:
            text = Page(path.read_text()).plain
            self.assertIn(self.result["attribution"], text)
            self.assertIn("a model result, not an observation", text)

    def test_every_page_names_its_address_on_the_domain(self):
        for path in self.written:
            attributes = Page(path.read_text()).attributes
            folder = str(path.parent.relative_to(self.directory))
            url = build_site.SITE_URL + ("" if folder == "." else folder + "/")
            self.assertIn(("link", {"rel": "canonical", "href": url}), attributes, path)
            self.assertIn(("meta", {"property": "og:url", "content": url}), attributes, path)
            self.assertNotIn("robots", [a.get("name") for _, a in attributes], path)


class Scenarios(unittest.TestCase):
    """Pages for states the committed data is not in right now."""

    def setUp(self):
        self.result = json.loads(run.OUTPUT_FILE.read_text())
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        # The last year with a result, whatever the season of the committed data.
        self.last_year = max(row["year"] for row in self.result["rows"])

    def not_yet(self, slug, year):
        """Put one city into the next year, before bloom."""
        city = next(c for c in self.result["cities"] if c["slug"] == slug)
        city["current"] = {"year": year, "status": "not_yet", "data_through": f"{year}-03-01"}
        return city

    def bloomed(self, slug, days_vs_baseline):
        """Put one city into bloom in the last year with a result."""
        city = next(c for c in self.result["cities"] if c["slug"] == slug)
        year = self.last_year
        city["current"] = {"year": year, "status": "bloomed", "data_through": f"{year}-06-30",
                           "bloom_doy": city["baseline_doy"] + days_vs_baseline,
                           "days_vs_baseline": days_vs_baseline}
        return city

    def test_after_bloom(self):
        current = self.bloomed("cologne", -7.72)["current"]
        build_site.build(self.result, self.directory)
        page = Page((self.directory / "cologne" / "index.html").read_text())
        year = current["year"]
        date = build_site.day_month(build_site.date_of(current["bloom_doy"], year))
        self.assertEqual(page.errors, [])
        self.assertIn(f"In {year} the modelled start of spring was 8 days earlier than "
                      "the 1991–2020 average.", page.plain)
        self.assertIn(f"Start of spring {year} {date}", page.plain)
        self.assertIn(f"spring {year} was 8 days earlier than usual", page.plain)
        self.assertNotIn("not arrived yet", page.plain)
        self.assertIn('<td data-value="-7.72">−8</td>',
                      (self.directory / "index.html").read_text())

    def test_before_bloom(self):
        year = self.last_year + 1
        for city in self.result["cities"]:
            self.not_yet(city["slug"], year)
        build_site.build(self.result, self.directory)

        page = Page((self.directory / "cologne" / "index.html").read_text())
        self.assertEqual(page.errors, [])
        self.assertIn("../method/", page.links)
        self.assertIn(f"The modelled start of spring has not arrived yet in {year}.", page.plain)
        self.assertIn(f"Temperatures received up to 1 March {year}", page.plain)
        self.assertIn(f"spring {year} has not started yet", page.plain)
        self.assertNotIn("earlier than", page.plain.split("Every year since")[0])
        # The city's latest result is still in the table.
        latest = max(r["year"] for r in self.result["rows"] if r["city"] == "cologne")
        self.assertIn(f'<th scope="row">{latest}</th>',
                      (self.directory / "cologne" / "index.html").read_text())

        index = Page((self.directory / "index.html").read_text())
        self.assertEqual(index.errors, [])
        self.assertEqual(index.plain.count("Not yet"), len(self.result["cities"]))

    def test_cities_in_different_years(self):
        """Around the turn of the year some cities can be a year ahead."""
        year = self.last_year + 1
        for city in self.result["cities"]:
            self.bloomed(city["slug"], -1.0)
        self.not_yet("cologne", year)
        build_site.build(self.result, self.directory)
        source = (self.directory / "index.html").read_text()
        self.assertIn('<th scope="col" data-sort="number">Year</th>', source)
        self.assertEqual(Page(source).errors, [])
        # The city not yet in bloom is listed last.
        self.assertEqual(max(source.index(f'<a href="{c["slug"]}/">')
                             for c in self.result["cities"]),
                         source.index('<a href="cologne/">'))

    def test_names_are_escaped(self):
        self.result["cities"][0]["name"] = "<b>Köln & Bonn</b>"
        build_site.build(self.result, self.directory)
        source = (self.directory / self.result["cities"][0]["slug"] / "index.html").read_text()
        self.assertNotIn("<b>Köln", source)
        self.assertIn("&lt;b&gt;Köln &amp; Bonn&lt;/b&gt;", source)

    def test_building_does_not_change_the_data(self):
        before = copy.deepcopy(self.result)
        build_site.build(self.result, self.directory)
        self.assertEqual(self.result, before)


@unittest.skipUnless(shutil.which("node"), "Node.js not installed")
class Sorting(unittest.TestCase):
    """The comparison used by static/sort.js."""

    def test_sort_order(self):
        script = """
        const { sortKey, compareKeys } = require(process.argv[1]);
        const sort = (values, numeric, descending) => values
          .map((v) => sortKey(v, numeric))
          .sort((a, b) => compareKeys(a, b, numeric, descending))
          .map((v) => (Number.isNaN(v) ? "" : v));
        console.log(JSON.stringify({
          ascending: sort(["1.3", "-7.7", "", "-0.04", "10", "2"], true, false),
          descending: sort(["1.3", "-7.7", "", "-0.04", "10", "2"], true, true),
          text: sort(["Munich", "Berlin", "Malmö", "Cologne"], false, false),
        }));
        """
        path = str(build_site.SITE_DIR / "static" / "sort.js")
        output = subprocess.run(["node", "-e", script, path], capture_output=True,
                                text=True, check=True).stdout
        self.assertEqual(json.loads(output), {
            "ascending": [-7.7, -0.04, 1.3, 2, 10, ""],
            "descending": [10, 2, 1.3, -0.04, -7.7, ""],
            "text": ["Berlin", "Cologne", "Malmö", "Munich"],
        })


if __name__ == "__main__":
    unittest.main()
