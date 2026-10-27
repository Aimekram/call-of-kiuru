"""
The site built from data/bloom.json: the wording and rounding helpers, and
the pages themselves.

Run from the repository root:
    python -m unittest -v tests.test_site

Needs no downloads. The table-sorting check runs if Node.js is installed.
"""

import copy
import csv
import datetime
import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from markupsafe import escape

from pipeline import build_site, run
from validation import bloom_stats

VOID = {"meta", "link", "br", "img", "hr", "input"}


def ranking_cell(source, days_vs_baseline):
    """The ranking's 'days from average' cell for one unrounded difference."""
    start = source.index(f'<td data-value="{days_vs_baseline}">')
    return source[start:source.index("</td>", start) + 5]


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

    def test_headline_phrase(self):
        self.assertEqual(build_site.headline_phrase(-7.72), "8 days early")
        self.assertEqual(build_site.headline_phrase(-1.2), "1 day early")
        self.assertEqual(build_site.headline_phrase(1.38), "1 day late")
        self.assertEqual(build_site.headline_phrase(-0.4), "on time")

    def test_tip_phrase(self):
        self.assertEqual(build_site.tip_phrase(-7.72), "8 days earlier")
        self.assertEqual(build_site.tip_phrase(1.2), "1 day later")
        self.assertEqual(build_site.tip_phrase(-0.4), "Same as the average")

    def test_rarity_phrase(self):
        def phrase(day, *days):
            return build_site.rarity_phrase(day, 2026, [{"bloom_doy": d} for d in days])
        # Unrounded: 109.67 is later than 109.33, though both show as the same date.
        self.assertEqual(phrase(109.67, 109.33, 110, 112), "1 of 3 came earlier than 2026")
        self.assertEqual(phrase(120, 110, 115, 125), "1 of 3 came later than 2026")
        self.assertEqual(phrase(120, 120, 119, 125, 130),
                         "1 of 4 came earlier than 2026, 1 on the same day of the year")
        self.assertEqual(phrase(100, 110, 120), "none of 2 came earlier than 2026")
        self.assertEqual(phrase(100, 100, 100, 120),
                         "none of 3 came earlier than 2026, 2 on the same day of the year")

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
        expected = {"index.html", "method/index.html", "accuracy/index.html", "privacy/index.html", "about/index.html"} | {
            f"{c['slug']}/index.html" for c in self.result["cities"]}
        self.assertEqual({str(p.relative_to(self.directory)) for p in self.written}, expected)
        self.assertTrue((self.directory / "static" / "style.css").exists())
        self.assertTrue((self.directory / "static" / "sort.js").exists())

    def test_pages_are_well_formed_and_links_resolve(self):
        for path in self.written:
            page = Page(path.read_text())
            self.assertEqual(page.errors, [], path)
            for link in page.links:
                if link.startswith(("https://", "mailto:")):
                    continue
                link_path, _, anchor = link.partition("#")
                target = (path.parent / link_path).resolve()
                self.assertTrue(target.is_dir() or target.exists(), f"{path}: {link}")
                if target.is_dir():
                    target = target / "index.html"
                    self.assertTrue(target.exists(), f"{path}: {link}")
                if anchor:
                    ids = {a.get("id") for _, a in Page(target.read_text()).attributes}
                    self.assertIn(anchor, ids, f"{path}: {link}")
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
                self.assertIn(f"spring {current['year']}", text)
                self.assertIn("Spring bloom has not come yet", text)
                self.assertIn("Temperatures received up to "
                              f"{build_site.day_month(through)} {through.year}", text)
                continue
            headline = build_site.headline_phrase(current["days_vs_baseline"])
            date = build_site.day_month(build_site.date_of(current["bloom_doy"], current["year"]))
            self.assertIn(f"spring {current['year']}", text)
            self.assertIn(f"Spring came {headline}", text)
            self.assertIn(f"Spring bloom {current['year']} {date}", text)

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

    def test_each_city_charts_every_year_on_one_scale(self):
        scale = build_site.chart_scale(self.result["rows"])
        largest = max(abs(build_site.whole_days(r["days_vs_baseline"])) for r in self.result["rows"])
        self.assertGreaterEqual(scale, largest)
        for city in self.result["cities"]:
            rows = sorted((r for r in self.result["rows"] if r["city"] == city["slug"]),
                          key=lambda r: r["year"])
            chart = build_site.trend_chart(rows, scale, (1991, 2020))
            self.assertEqual([b["year"] for b in chart["bars"]], [r["year"] for r in rows])
            for bar, row in zip(chart["bars"], rows):
                days = build_site.whole_days(row["days_vs_baseline"])
                # A bar for every year that is not 0, on the side its sign says.
                self.assertEqual(bar["d"] == "", days == 0, (city["slug"], row["year"]))
                self.assertEqual(bar["side"], "early" if days < 0 else "late")
                self.assertEqual(bar["key"], "" if days == 0 else bar["side"])
                self.assertEqual(bar["tip"], build_site.tip_phrase(row["days_vs_baseline"]))
            source = (self.directory / city["slug"] / "index.html").read_text()
            self.assertEqual(source.count('class="hit"'), len(rows), city["slug"])
            self.assertIn('static/chart.js', source)

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
        self.assertTrue(any("wmo.int" in link for link in page.links))

    def test_privacy_page_names_who_and_what(self):
        page = Page((self.directory / "privacy" / "index.html").read_text())
        for text in (build_site.CONTROLLER, build_site.ADDRESS, build_site.CONTACT, "GitHub Pages", "GoatCounter", "UODO",
                     "Data Privacy Framework", "Article 6(1)(f)", "data protection authority"):
            self.assertIn(text, page.plain)
        # The tip link's clicks are counted as a GoatCounter event.
        if build_site.TIP_URL:
            source = (self.directory / "index.html").read_text()
            self.assertIn(f'href="{build_site.TIP_URL}" data-goatcounter-click="tip-link"', source)
        # Every page links to it from the footer.
        for path in self.written:
            if path.name == "index.html":
                self.assertIn("privacy/", " ".join(Page(path.read_text()).links), path)

    def test_every_page_names_a_share_card_that_is_made(self):
        from pipeline import share_cards
        names = {name for name, _ in share_cards.card_pages(self.result)}
        width, height = build_site.CARD_SIZE
        for path in self.written:
            attributes = dict((a.get("property") or a.get("name"), a.get("content"))
                              for tag, a in Page(path.read_text()).attributes if tag == "meta")
            image = attributes["og:image"]
            self.assertTrue(image.startswith(build_site.SITE_URL + "cards/"), path)
            self.assertIn(image.rsplit("/", 1)[1].removesuffix(".png"), names, path)
            self.assertEqual((attributes["og:image:width"], attributes["og:image:height"]),
                             (str(width), str(height)), path)
            self.assertTrue(attributes["og:image:alt"], path)
            self.assertEqual(attributes["twitter:card"], "summary_large_image", path)

    def test_card_pages_render(self):
        from pipeline import share_cards
        for card_format in share_cards.FORMATS:
            folder = self.directory / "_cards" / card_format
            names = share_cards.write_card_pages(self.result, folder, card_format)
            for city in self.result["cities"]:
                page = Page((folder / f"{city['slug']}.html").read_text())
                self.assertEqual(page.errors, [], (card_format, city["slug"]))
                self.assertIn(f"{city['name']}, {city['country']}", page.plain)
            self.assertIn("ranking", names)
            self.assertIn("site", names)
        shutil.rmtree(self.directory / "_cards")

    def test_method_page_explains_the_model(self):
        page = Page((self.directory / "method" / "index.html").read_text())
        ids = {a.get("id") for _, a in page.attributes}
        self.assertLessEqual({"model", "coverage", "baseline"}, ids)
        self.assertTrue(any("usanpn.org" in link for link in page.links))
        self.assertIn("https://doi.org/10.1002/joc.3625", page.links)
        self.assertIn("../accuracy/", page.links)

    def test_accuracy_page_shows_the_validation(self):
        page = Page((self.directory / "accuracy" / "index.html").read_text())
        self.assertEqual(page.errors, [])
        self.assertIn("../method/#model", page.links)
        # The observers' data are credited where they are used, each licence
        # linked to its text.
        self.assertIn("based on data from Deutscher Wetterdienst ( CC BY 4.0 ) and from "
                      "SLU Naturens Kalender ( CC0 ).", page.plain)
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", page.links)
        self.assertIn("https://creativecommons.org/publicdomain/zero/1.0/", page.links)
        # The bloom test's by-country figures (run_bloom_test.py, 20 cities, 2026-10-20).
        for figure in ("0.92 0.89–0.95", "0.72 0.54–0.87", "0.82 0.73–0.88",
                       "0.52 0.25–0.75", "3.8 days 3.2–4.3", "3.9 days 2.6–4.8"):
            self.assertIn(figure, page.plain)
        # The European benchmark is linked.
        self.assertIn("https://www.nature.com/articles/s41597-024-03710-5", page.links)

    def test_accuracy_page_charts_each_city_against_observed_bloom(self):
        rows = build_site.check_rows()
        self.assertEqual(set(rows), {c["slug"] for c in self.result["cities"]})
        low, high = build_site.check_scale(rows)
        source = (self.directory / "accuracy" / "index.html").read_text()
        self.assertEqual(Page(source).errors, [])
        self.assertEqual(source.count("data-check"), len(rows))
        self.assertEqual(source.count('class="hit"'), sum(len(years) for years in rows.values()))
        for slug, years in rows.items():
            self.assertIn(f'<a href="../{slug}/">', source)
            for r in years:
                self.assertTrue(low <= min(r["model"], r["observed"]) <= max(r["model"], r["observed"]) <= high)
        # Berlin 1951 in data/bloom_multiyear.csv: model day 136.67, observed day 133, 17 observations.
        self.assertIn('data-year="1951" data-observed="13 May" data-model="17 May"', source)
        self.assertIn('data-n="median of 17 observations"', source)
        self.assertIn('static/chart.js', source)

    def grades(self):
        """data/bloom_grades.csv by city name."""
        names = {c["key"]: c["name"] for c in run.load_locations()}
        with build_site.GRADES_FILE.open(newline="") as f:
            return {names[r["location"]]: r for r in csv.DictReader(f)}

    def test_city_pages_show_how_well_the_model_does_there(self):
        grades = self.grades()
        # Every city on the site has been tested (PLAN.md §3).
        self.assertEqual(set(grades), {c["name"] for c in self.result["cities"]})
        for city in self.result["cities"]:
            g = grades[city["name"]]
            low = float(g["skill_low"])
            self.assertEqual(g["grade"], bloom_stats.grade(low))
            source = (self.directory / city["slug"] / "index.html").read_text()
            label, shown = build_site.GRADE_LABELS[g["grade"]], build_site.cautious_score(low, g["grade"])
            self.assertIn(f"Track record {label}", Page(source).plain)
            self.assertIn(f"Skill score {build_site.score(float(g['skill']))} "
                          f'(<a href="../accuracy/#range">95% range</a> {shown} to', source)
            self.assertIn(f"<strong>{label}</strong>. Even at the cautious end of the range ({shown}), "
                          f"{escape(build_site.GRADE_REASONS[g['grade']])}.", source)
            # Signal bars, in the facts row and the section.
            self.assertEqual(source.count('class="on"'), 2 * build_site.GRADE_LEVELS[g["grade"]])

    def test_accuracy_page_explains_the_grades(self):
        grades = self.grades()
        source = (self.directory / "accuracy" / "index.html").read_text()
        page = Page(source)
        self.assertIn("grades", {a.get("id") for _, a in page.attributes})
        self.assertIn("https://doi.org/10.1175/1520-0493(1988)116%3C2417:SSBOTM%3E2.0.CO;2", page.links)
        for name, g in grades.items():
            # Each chart's caption carries the city's grade.
            caption = source[source.index(f">{name}</a> <small>"):]
            caption = caption[:caption.index("</figcaption>")]
            self.assertTrue(caption.endswith(f"{build_site.GRADE_LABELS[g['grade']]}</span>"), name)
        unconfirmed = [g for g in grades.values() if g["grade"] == "unconfirmed"]
        self.assertIn(f"confirmed in {len(grades) - len(unconfirmed)} of the {len(grades)} cities", page.plain)
        # The page says those are so far only Swedish, with 16 or 17 springs:
        # if that stops being true, the sentence in method.html has to change.
        for g in unconfirmed:
            self.assertTrue(g["location"].endswith(", Sweden") and g["springs"] in ("16", "17"), g["location"])

    def test_scores(self):
        self.assertEqual(build_site.score(0.836), "0.84")
        self.assertEqual(build_site.score(-0.03), "−0.03")
        self.assertEqual(build_site.score(-0.001), "0.00")
        # Beside a grade, a third decimal only where rounding would cross a line.
        self.assertEqual(build_site.cautious_score(0.496, "fair"), "0.496")
        self.assertEqual(build_site.cautious_score(0.4996, "fair"), "0.4996")
        self.assertEqual(build_site.cautious_score(0.004, "fair"), "0.004")
        self.assertEqual(build_site.cautious_score(-0.004, "unconfirmed"), "0.00")

    def test_about_page_explains_the_name_and_links_out(self):
        page = self.page("about/index.html")
        self.assertEqual(page.errors, [])
        self.assertIn("Kiuru is Finnish for the skylark", page.plain)
        self.assertIn("Kuu kiurusta kesään", page.plain)
        self.assertIn(build_site.SAYING_SOURCE, page.links)
        self.assertIn("../method/", page.links)
        self.assertIn("https://www.usanpn.org/data/maps/spring", page.links)
        self.assertIn(build_site.BLUESKY_URL, page.links)
        self.assertIn(build_site.INSTAGRAM_URL, page.links)
        # Linked from every page's footer.
        for path in self.written:
            self.assertTrue(any(link.endswith("about/") for link in Page(path.read_text()).links), path)

    def test_404_page_works_at_any_address_and_is_not_indexed(self):
        source = (self.directory / "404.html").read_text()
        page = Page(source)
        self.assertEqual(page.errors, [])
        self.assertIn('<meta name="robots" content="noindex">', source)
        self.assertNotIn("canonical", source)
        self.assertNotIn("404", (self.directory / "sitemap.xml").read_text())
        # Served at any address, so links start at the site root and resolve from it.
        for link in page.links:
            if link.startswith(("https://", "mailto:")):
                continue
            self.assertTrue(link.startswith("/"), link)
            target = self.directory / link.lstrip("/")
            self.assertTrue((target / "index.html").exists() or target.exists(), link)
        for tag, attributes in page.attributes:
            asset = attributes.get("href") or attributes.get("src")
            if tag in ("link", "script") and asset and not asset.startswith("https://"):
                self.assertTrue(asset.startswith("/"), asset)
                self.assertTrue((self.directory / asset.lstrip("/")).exists(), asset)
        self.assertEqual(source.count('class="floret'), len(build_site.lilac_sprig()))

    def test_sitemap_lists_every_page_by_its_canonical_url(self):
        tree = ElementTree.parse(self.directory / "sitemap.xml")
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        listed = [loc.text for loc in tree.iter(f"{namespace}loc")]
        canonical = [next(a["href"] for tag, a in self.page(p).attributes
                          if tag == "link" and a.get("rel") == "canonical")
                     for p in self.written]
        self.assertEqual(sorted(listed), sorted(canonical))
        self.assertEqual(len(set(listed)), len(listed))
        robots = (self.directory / "robots.txt").read_text()
        self.assertIn(f"Sitemap: {build_site.SITE_URL}sitemap.xml", robots)
        self.assertNotIn("Disallow", robots)

    def test_the_average_links_to_its_explanation(self):
        self.assertIn('<a href="method/#baseline">1991–2020 average</a>',
                      (self.directory / "index.html").read_text())
        for city in self.result["cities"]:
            self.assertIn('<dt><a href="../method/#baseline">1991–2020 average</a></dt>',
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
            days = city["current"]["days_vs_baseline"]
            cell = ranking_cell(source, days)
            self.assertIn(f'<span class="number">{build_site.signed_days(days)}</span>', cell)
            # The bar shows the whole days printed beside it, on the side they fall.
            side = "early" if build_site.whole_days(days) < 0 else "late"
            self.assertIn(f'<span class="{side}" style="width: ', cell)

    def test_every_page_with_data_carries_the_attribution_and_the_caveat(self):
        for path in self.written:
            text = Page(path.read_text()).plain
            if path.parent.name in ("privacy", "about"):
                # The privacy and about pages show no data.
                self.assertNotIn(self.result["attribution"], text)
                continue
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
        self.assertIn("Spring came 8 days early", page.plain)
        self.assertIn(f"Spring bloom {year} {date}", page.plain)
        self.assertIn(f"spring {year} was 8 days earlier than usual", page.plain)
        self.assertNotIn("has not come yet", page.plain)
        # Counted against the springs before this one, on unrounded days.
        before = [r for r in self.result["rows"] if r["city"] == "cologne" and r["year"] < year]
        earlier = sum(r["bloom_doy"] < current["bloom_doy"] for r in before)
        later = sum(r["bloom_doy"] > current["bloom_doy"] for r in before)
        self.assertIn(f"Springs 1940–{year - 1} {min(earlier, later)} of {len(before)} came "
                      f"{'earlier' if earlier <= later else 'later'} than {year}", page.plain)
        cell = ranking_cell((self.directory / "index.html").read_text(), -7.72)
        self.assertIn('<span class="number">−8</span>', cell)
        # Each half of the bar is at least 10 days, so 8 days is 40% of the whole bar.
        self.assertIn('<span class="early" style="width: 40.0%">', cell)

    def test_before_bloom(self):
        year = self.last_year + 1
        for city in self.result["cities"]:
            self.not_yet(city["slug"], year)
        build_site.build(self.result, self.directory)

        page = Page((self.directory / "cologne" / "index.html").read_text())
        self.assertEqual(page.errors, [])
        self.assertIn("../method/#baseline", page.links)
        self.assertIn(f"spring {year}", page.plain)
        self.assertIn("Spring bloom has not come yet", page.plain)
        self.assertIn(f"Temperatures received up to 1 March {year}", page.plain)
        self.assertIn(f"spring bloom {year} has not come yet", page.plain)
        self.assertNotIn("earlier than", page.plain.split("Every year since")[0])
        self.assertNotIn("Springs 1940", page.plain)
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
