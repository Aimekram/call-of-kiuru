#!/usr/bin/env python3
"""
Make the share cards for the site in site/dist/: one per city, one for the
ranking and one for the other pages, in two formats:
- link previews (og:image), 1200x630, in cards/<name>.png;
- Instagram posts, 1080x1350, in cards/instagram/<name>.png.
Run after build_site.

Each card is an HTML page in the site's own style, photographed with headless
Chrome. The card pages are served from site/dist so the site's fonts load,
then removed.

Usage:
    python -m pipeline.build_site && python -m pipeline.share_cards

Needs Chrome. Set CHROME to its path if it isn't found.
"""

import functools
import json
import os
import shutil
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pipeline import build_site, run

# Format name: (size, folder under site/dist).
FORMATS = {
    "link": (build_site.CARD_SIZE, "cards"),
    "instagram": ((1080, 1350), "cards/instagram"),
}

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def card_pages(result, card_format="link"):
    """(name, context) for every card. The names match the og:image of each page."""
    cities, ranking, shared = build_site.prepare(result)
    pages = [(city["slug"], {"kind": "city", "city": city}) for city in cities]
    pages.append(("ranking", {"kind": "ranking", "cities": ranking}))
    pages.append(("site", {"kind": "site", "cities": cities}))
    (width, height), _ = FORMATS[card_format]
    size = {"card_format": card_format, "card_width": width, "card_height": height}
    return [(name, {**shared, **context, **size, "root": "../../"}) for name, context in pages]


def write_card_pages(result, folder, card_format="link"):
    """Render each card as an HTML page in folder (two levels under the site).
    Returns the card names."""
    folder.mkdir(parents=True, exist_ok=True)
    template = build_site.environment().get_template("card.html")
    names = []
    for name, context in card_pages(result, card_format):
        (folder / f"{name}.html").write_text(template.render(**context))
        names.append(name)
    return names


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def find_chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for path in CHROME_PATHS:
        if Path(path).exists() or shutil.which(path):
            return path
    raise SystemExit("Chrome not found; set CHROME to its path.")


def photograph(chrome, url, target, size):
    width, height = size
    options = ["--headless=new", "--disable-gpu", "--hide-scrollbars",
               "--force-device-scale-factor=1", f"--window-size={width},{height}",
               "--virtual-time-budget=5000", f"--screenshot={target}"]
    if os.environ.get("CI"):
        # CI runners on recent Ubuntu block Chrome's sandbox; the pages are our own.
        options.append("--no-sandbox")
    subprocess.run([chrome, *options, url], check=True, capture_output=True, timeout=60)
    if not target.exists():
        raise SystemExit(f"Chrome made no image for {url}")


def main():
    result = json.loads(run.OUTPUT_FILE.read_text())
    site = build_site.OUTPUT_DIR
    pages = site / "_cards"
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    made = 0
    try:
        chrome = find_chrome()
        for card_format, (size, folder) in FORMATS.items():
            names = write_card_pages(result, pages / card_format, card_format)
            (site / folder).mkdir(parents=True, exist_ok=True)
            for name in names:
                photograph(chrome, f"http://127.0.0.1:{server.server_port}/_cards/{card_format}/{name}.html",
                           site / folder / f"{name}.png", size)
                made += 1
    finally:
        server.shutdown()
        shutil.rmtree(pages, ignore_errors=True)
    print(f"✓ Made {made} share cards in {site / 'cards'}")


if __name__ == "__main__":
    main()
