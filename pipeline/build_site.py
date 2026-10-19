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
OWNER = "nin at devtortie"
CONTROLLER = "Devtortie Janina Byszewska"  # as registered in CEIDG
ADDRESS = "ul. Stanisława Taczaka 24/103, 61-819 Poznań, Poland"  # CEIDG place of business
CONTACT = "hello@callofkiuru.eu"
PRIVACY_UPDATED = "18 October 2026"
TIP_URL = "https://suppi.pl/devtortie"
# Share cards (og:image), made by share_cards.py into cards/.
CARD_SIZE = (1200, 630)
SITE_CARD_ALT = "Call of Kiuru: the modelled start of spring in European cities, every year since 1940."
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


def headline_phrase(days_vs_baseline):
    """'8 days early', '1 day late' or 'on time', for whole days."""
    days = whole_days(days_vs_baseline)
    if days == 0:
        return "on time"
    unit = "day" if abs(days) == 1 else "days"
    return f"{abs(days)} {unit} {'early' if days < 0 else 'late'}"


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


# The trend chart's plot is this many CSS pixels tall at every width (the
# same 200px is in style.css). Bars are drawn on a 1000-unit-wide box
# stretched to the plot's width, so labels can stay HTML text at their size.
CHART_HEIGHT = 200
CHART_WIDTH = 1000


def tip_phrase(days_vs_baseline):
    """'8 days earlier', '1 day later' or 'Same as the average', for whole days."""
    days = whole_days(days_vs_baseline)
    if days == 0:
        return "Same as the average"
    unit = "day" if abs(days) == 1 else "days"
    return f"{abs(days)} {unit} {'earlier' if days < 0 else 'later'}"


def chart_scale(rows):
    """Days from the line to the top (and bottom) of every city's chart: the
    largest whole-day difference in any city, up to the next 10, at least 20."""
    largest = max(abs(whole_days(r["days_vs_baseline"])) for r in rows)
    return max(20, math.ceil(largest / 10) * 10)


def trend_chart(rows, scale, baseline_years):
    """Geometry and labels for one city's bars, oldest year first. Bars show
    whole days, like the table beside them."""
    rows = sorted(rows, key=lambda r: r["year"])
    zero = CHART_HEIGHT / 2

    def y(days):
        return zero - days / scale * (zero - 4)
    step = CHART_WIDTH / len(rows)
    width = step * 0.68
    ry = 2  # the rounded outer end, in px
    first, last = baseline_years

    def pct(x):
        return f"{x / CHART_WIDTH * 100:.2f}"

    bars = []
    for i, r in enumerate(rows):
        days = whole_days(r["days_vs_baseline"])
        x = i * step + (step - width) / 2
        end = y(days)
        if days == 0:
            d = ""
        elif abs(end - zero) <= ry:
            d = f"M{x:.2f},{zero:.2f}V{end:.2f}H{x + width:.2f}V{zero:.2f}Z"
        elif days > 0:
            d = (f"M{x:.2f},{zero:.2f}V{end + ry:.2f}A{width / 2:.2f},{ry} 0 0 1 "
                 f"{x + width:.2f},{end + ry:.2f}V{zero:.2f}Z")
        else:
            d = (f"M{x:.2f},{zero:.2f}V{end - ry:.2f}A{width / 2:.2f},{ry} 0 0 0 "
                 f"{x + width:.2f},{end - ry:.2f}V{zero:.2f}Z")
        side = "early" if days < 0 else "late"
        bars.append({"d": d, "side": side, "key": side if days else "",
                     "hit_x": f"{i * step:.2f}", "hit_width": f"{step:.2f}",
                     "x": pct(i * step + step / 2), "year": r["year"],
                     "date": day_month(date_of(r["bloom_doy"], r["year"])),
                     "tip": tip_phrase(r["days_vs_baseline"])})

    years = [r["year"] for r in rows]
    band_start = years.index(first) * step if first in years else 0
    band_end = (years.index(last) + 1) * step if last in years else CHART_WIDTH
    grid = [{"y": f"{y(v):.2f}", "top": f"top: {y(v):.1f}px",
             "label": "0" if v == 0 else f"{'+' if v > 0 else '−'}{abs(v)}"}
            for v in range(-scale, scale + 1, 10)]
    newest = bars[-1]
    return {
        "height": CHART_HEIGHT, "width": CHART_WIDTH, "zero": f"{zero:.2f}",
        "bars": bars, "grid": grid,
        "band": {"x": f"{band_start:.2f}", "width": f"{band_end - band_start:.2f}",
                 "label_x": f"--x: {pct((band_start + band_end) / 2)}"},
        "years": [{"label": b["year"], "x": f"--x: {b['x']}"} for b in bars
                  if b["year"] % 20 == 0],
        # Shown in the tooltip until someone points at another year.
        "newest": {**newest, "style": f"--x: {newest['x']}"},
        "first_year": years[0], "last_year": years[-1],
    }


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
                    headline=headline_phrase(current["days_vs_baseline"]),
                    signed_days=signed_days(current["days_vs_baseline"]),
                    sort_days=current["days_vs_baseline"], sort_date=current["bloom_doy"])
    return view


def environment():
    return Environment(loader=FileSystemLoader(SITE_DIR / "templates"),
                       autoescape=select_autoescape(["html"]),
                       undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


def prepare(result):
    """The cities (in data order), the ranking, and what every template
    shares, for one pipeline output. Used by the pages and the share cards."""
    cities = [city_view(city, [r for r in result["rows"] if r["city"] == city["slug"]])
              for city in result["cities"]]
    # Earliest compared with its own average first; cities not yet in bloom last.
    ranking = sorted(cities, key=lambda c: (not c["bloomed"], c.get("sort_days", 0), c["name"]))
    # Ranking bars show the whole days printed beside them, on one scale for
    # all cities: at least 10 days for a full half-bar.
    bloomed = [c for c in cities if c["bloomed"]]
    scale = max([10] + [abs(whole_days(c["sort_days"])) for c in bloomed])
    for city in bloomed:
        days = whole_days(city["sort_days"])
        city["meter"] = {"side": "early" if days < 0 else "late",
                         "width": f"{abs(days) / scale * 50:.1f}%"}
    first, last = result["baseline_years"]
    chart_days = chart_scale(result["rows"])
    for city in cities:
        city["chart"] = trend_chart([r for r in result["rows"] if r["city"] == city["slug"]],
                                    chart_days, (first, last))
    shared = {
        "site_name": SITE_NAME,
        "owner": OWNER, "contact": CONTACT, "tip_url": TIP_URL,
        "baseline": f"{first}–{last}",
        "baseline_length": last - first + 1,
        "attribution": result["attribution"],
        "updated": day_month(datetime.date.fromisoformat(result["generated"]))
                   + f" {result['generated'][:4]}",
        "site_url": SITE_URL, "card_width": CARD_SIZE[0], "card_height": CARD_SIZE[1],
        "year": sorted({c["year"] for c in cities})[-1],
        "mixed_years": len({c["year"] for c in cities}) > 1,
    }
    for city in cities:
        city["card_alt"] = (
            f"{city['name']}: spring {city['year']} came {city['headline']}"
            if city["bloomed"] else f"{city['name']}: spring {city['year']} has not come yet"
        ) + f". Bars for every spring since {city['chart']['first_year']}, earlier or later than the {shared['baseline']} average."
    return cities, ranking, shared


def build(result, output_dir=OUTPUT_DIR):
    """Write the site for one pipeline output. Returns the files written."""
    templates = environment()
    cities, ranking, shared = prepare(result)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(SITE_DIR / "static", output_dir / "static")
    written = []

    def write(path, template, **context):
        target = output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        url = SITE_URL + path.removesuffix("index.html")
        target.write_text(templates.get_template(template).render(**shared, **context, url=url))
        written.append(target)

    # Each page names its share card (made by share_cards.py) and describes it.
    write("index.html", "index.html", cities=ranking, root="", card="ranking",
          card_alt=f"Start of spring {shared['year']} in {len(cities)} cities, earliest first.")
    for city in cities:
        write(f"{city['slug']}/index.html", "city.html", city=city, root="../",
              card=city["slug"], card_alt=city["card_alt"])
    gaps = [c["earlier_gap"] for c in cities]
    write("privacy/index.html", "privacy.html", root="../", card="site", card_alt=SITE_CARD_ALT,
          privacy_updated=PRIVACY_UPDATED,
          controller=CONTROLLER, address=ADDRESS)
    write("method/index.html", "method.html", root="../", card="site", card_alt=SITE_CARD_ALT,
          cities=sorted(cities, key=lambda c: c["sort_usual"]),
          earlier="{}–{}".format(*EARLIER_YEARS),
          earlier_gap_least=whole_days(min(gaps)), earlier_gap_most=whole_days(max(gaps)))
    return written


def main():
    written = build(json.loads(run.OUTPUT_FILE.read_text()))
    print(f"✓ Wrote {len(written)} pages to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
