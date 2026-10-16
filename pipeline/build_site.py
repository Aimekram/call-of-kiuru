#!/usr/bin/env python3
"""
Build the static site from data/bloom.json into site/dist/: a ranking of
all cities, one page per city, and a page on how the average is worked out.

This is the only place where numbers are rounded. Everything is read from
data/bloom.json as stored; days are rounded to whole days here, for reading
(the averages on the method page to one decimal).

Usage:
    python -m pipeline.build_site
    python -m http.server --directory site/dist      # then open localhost:8000
"""

import datetime
import json
import math
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from pipeline import run

SITE_DIR = Path(__file__).parent.parent / "site"
OUTPUT_DIR = SITE_DIR / "dist"
SITE_NAME = "Call of Kiuru"
SITE_URL = "https://callofkiuru.eu/"
# The 30 years before the baseline, shown on the method page for comparison.
# The WMO reference period for long-term climate change.
EARLIER_YEARS = (1961, 1990)


def whole_days(value):
    """Round to the nearest whole day, halves away from zero. Never -0."""
    rounded = math.floor(abs(value) + 0.5)
    return -rounded if value < 0 and rounded else rounded


def difference_phrase(days_vs_baseline):
    """'8 days earlier than', '1 day later than' or 'the same as', for whole days."""
    days = whole_days(days_vs_baseline)
    if days == 0:
        return "the same as"
    unit = "day" if abs(days) == 1 else "days"
    return f"{abs(days)} {unit} {'earlier' if days < 0 else 'later'} than"


def signed_days(days_vs_baseline):
    """'−8', '+1' or '0': whole days, with a real minus sign."""
    days = whole_days(days_vs_baseline)
    return "0" if days == 0 else f"{'−' if days < 0 else '+'}{abs(days)}"


def date_of(day_of_year, year):
    """The calendar date of a (fractional) day of year in a given year."""
    return datetime.date(year, 1, 1) + datetime.timedelta(days=whole_days(day_of_year) - 1)


def day_month(date):
    return f"{date.day} {date:%B}"


def usual_date(baseline_doy):
    """A 30-year average day of year as a day and month, on a 365-day calendar."""
    return day_month(date_of(baseline_doy, 2023))


def earlier_gap(city, rows):
    """How many days later the EARLIER_YEARS mean is than the city's baseline."""
    first, last = EARLIER_YEARS
    days = [r["bloom_doy"] for r in rows if first <= r["year"] <= last]
    if len(days) != last - first + 1:
        raise ValueError(f"{city['slug']}: {len(days)} years in {first}-{last}")
    return sum(days) / len(days) - city["baseline_doy"]


def city_view(city, rows):
    """Everything a template needs for one city, already worded and rounded."""
    current = city["current"]
    years = [{"year": r["year"],
              "date": day_month(date_of(r["bloom_doy"], r["year"])),
              "iso_date": date_of(r["bloom_doy"], r["year"]).isoformat(),
              "signed_days": signed_days(r["days_vs_baseline"]),
              "sort_days": r["days_vs_baseline"], "sort_date": r["bloom_doy"]}
             for r in sorted(rows, key=lambda r: -r["year"])]
    view = {
        "slug": city["slug"], "name": city["name"], "country": city["country"],
        "usual_date": usual_date(city["baseline_doy"]),
        "usual_day": f"{city['baseline_doy']:.1f}",
        "sort_usual": city["baseline_doy"],
        "earlier_gap": earlier_gap(city, rows),
        "year": current["year"],
        "bloomed": current["status"] == "bloomed",
        "data_through": day_month(datetime.date.fromisoformat(current["data_through"]))
                        + f" {current['data_through'][:4]}",
        "years": years,
    }
    if view["bloomed"]:
        date = date_of(current["bloom_doy"], current["year"])
        view.update(date=day_month(date), iso_date=date.isoformat(),
                    phrase=difference_phrase(current["days_vs_baseline"]),
                    signed_days=signed_days(current["days_vs_baseline"]),
                    sort_days=current["days_vs_baseline"], sort_date=current["bloom_doy"])
    return view


def build(result, output_dir=OUTPUT_DIR):
    """Write the site for one pipeline output. Returns the files written."""
    environment = Environment(loader=FileSystemLoader(SITE_DIR / "templates"),
                              autoescape=select_autoescape(["html"]),
                              undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    cities = [city_view(city, [r for r in result["rows"] if r["city"] == city["slug"]])
              for city in result["cities"]]
    # Earliest compared with its own average first; cities not yet in bloom last.
    ranking = sorted(cities, key=lambda c: (not c["bloomed"], c.get("sort_days", 0), c["name"]))
    first, last = result["baseline_years"]
    shared = {
        "site_name": SITE_NAME,
        "baseline": f"{first}–{last}",
        "baseline_length": last - first + 1,
        "attribution": result["attribution"],
        "updated": day_month(datetime.date.fromisoformat(result["generated"]))
                   + f" {result['generated'][:4]}",
    }

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(SITE_DIR / "static", output_dir / "static")
    written = []

    def write(path, template, **context):
        target = output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        url = SITE_URL + path.removesuffix("index.html")
        target.write_text(environment.get_template(template).render(**shared, **context, url=url))
        written.append(target)

    years = sorted({c["year"] for c in cities})
    write("index.html", "index.html", cities=ranking, root="",
          year=years[-1], mixed_years=len(years) > 1)
    for city in cities:
        write(f"{city['slug']}/index.html", "city.html", city=city, root="../")
    gaps = [c["earlier_gap"] for c in cities]
    write("method/index.html", "method.html", root="../",
          cities=sorted(cities, key=lambda c: c["sort_usual"]),
          earlier="{}–{}".format(*EARLIER_YEARS),
          earlier_gap_least=whole_days(min(gaps)), earlier_gap_most=whole_days(max(gaps)))
    return written


def main():
    written = build(json.loads(run.OUTPUT_FILE.read_text()))
    print(f"✓ Wrote {len(written)} pages to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
