# Call of Kiuru — Build Plan

A European phenology dashboard: for each tracked city, show how many days
earlier or later spring arrived this year than in 1991–2020, modelled from
open climate data. Shareable, and honest about its own uncertainty.

"Spring" means the SI-x bloom index (first lilac bloom).

---

## 1. MVP scope (decided 2026-10-11)

**Cities: the 8 already validated.** Berlin, Munich, Cologne, Frankfurt,
Hamburg, Stockholm, Gothenburg, Malmö. A city is added only after it passes
the same test (§3).

**In:**
- A page per city: days early/late this year vs the 1991–2020 baseline, with
  a share card (Open Graph tags baked in).
- A ranking table of all cities.
- A trend chart per city: modelled bloom date for every year back to 1940.
- A methodology page showing the validation evidence and its limits.

**Out, for later (§6):** map view, location search, email digest, a
database, cities outside the validated zones, leaf-out and other events.

**Before bloom, the page says "not yet".** SI-x gives a bloom date only
once the year's weather has reached it. Until then the page shows the usual
date and last year's result. A forecast would need a published method; we
don't invent one (USA-NPN's goes 6 days ahead, see §6).

**Timing (proposed): live before March 2027.** The number only moves in
spring, and the earliest modelled bloom in the test is late March (Cologne
2024). Out of season the site shows the last completed spring and the
history.

---

## 2. Data pipeline

**Built (2026-10-12): steps 1 to 6.** `python -m pipeline.run` writes
`data/bloom.json` for the 8 cities: 696 rows, 1940–2026. A normal run takes
about 7 minutes, nearly all of it waiting for 8 small CDS requests. Tests in
`tests/test_pipeline.py` tie the output to the USA-NPN reference. Still to
build: the daily job (step 7). The site (step 8) has its first pages, see
§5.

**Step 1 — Dataset.** `reanalysis-era5-single-levels-timeseries`: hourly 2m
temperature at the nearest ERA5 grid point, reduced to daily max/min. This
is what the validation ran on, so production uses the same. One request
covers a city's whole history. It runs 5 to 6 days behind, and the newest
day can arrive as empty values, so the pipeline uses full days only and
stops at the first gap. Fallback:
`derived-era5-single-levels-daily-statistics`, which averages a 3×3 box and
gave a different result on the coast (Malmö 2020 bloom: day 133 vs 125).

Licensing rules are in §4.

**Step 2 — Locations as data, not code.** Rows of (name, lat, lon, zone),
never a hardcoded enum. Adding a city is "add a row, run the test".

**Step 3 — Historical pull.** 1940–present per city. 1991–2020 is the
baseline; the rest feeds the trend chart.

**Step 4 — Model.** The published SI-x leaf and bloom models, unmodified
(`validation/si_x_model.py`), with the published coefficients. Only bloom is
shown. The leaf index stays hidden: it was about 13 days early on average in
the 2024 paper's European check, and weeks early in ours (2020 only, few
observations). SI-x has no chilling term, which may be why; that is our
guess, not a tested finding.

**Rule: published models only, nothing fitted.** No correction constants,
no custom terms. Any deviation gets flagged and decided first.

**Step 5 — Baseline, then current year.** Modelled bloom day per year →
mean of 1991–2020 → the city's baseline. The displayed number is this
year's modelled day minus that baseline, so a constant per-city model bias
cancels out. 1991–2020 because it is the WMO's current climatological
standard normal, and the period USA-NPN's spring maps use. It is a recent
normal: the modelled 1961–1990 average is 4 to 11 days later in the 8
cities. The site's method page (`method/`) explains all of this.

**Step 6 — Store results.** One row per (city, year): modelled day, delta
vs baseline. About 700 rows in total, kept as a JSON file (`data/bloom.json`)
that the daily job writes and commits to the repo. Past years are read back
from the file; only the recent period is downloaded each day. Values are
stored as computed and rounded only where they are displayed. No database: nothing queries the data
at view time, and rows in this shape load straight into a table later.

**Step 7 — Daily refresh.** GitHub Actions, `on: schedule`. CDS requests
queue and can take far longer than expected, so give the job a timeout and
let a failed run skip to tomorrow. A day's delay doesn't matter.

**Step 8 — Regenerate the static site** as the last step of the same job,
so pages and data never drift apart.

---

## 3. Model validation

**Result (2026-10-11).** SI-x bloom vs observed lilac first bloom, every
year each network covers, nothing fitted (`docs/bloom_multiyear.md`,
`run_bloom_test.py`). Correlation and error are for anomalies, which is
what the app shows; intervals are 95%.

| | Springs | Correlation | Error vs normal-year | RMSE, bias |
|---|---|---|---|---|
| Germany, 5 cities, 1951–2024 | 74 | **0.92** (0.88 to 0.94) | 3.9 vs 8.9 days | 5.5, −3.7 |
| Sweden, 3 cities, 2008–2024 | 17 | **0.69** (0.46 to 0.87) | 4.6 vs 6.4 days | 5.0, −0.3 |

**Germany is solid.**
- It holds in every period: correlation 0.89 for 1951–1978, 0.90 for
  1979–2009, 0.94 for 2010–2024.
- It is not just the warming trend: with each city's trend removed the
  correlation is 0.89.
- The modelled trend matches the lilacs: 2.0 to 2.7 days earlier per decade
  modelled, 1.8 to 2.6 observed. This is the evidence behind the trend
  chart from 1951 on.
- The model runs 3.7 days early on average (per city −1.7 to −4.9). The
  app's number is relative to the model's own baseline, so this cancels.
- That bias is the honeysuckles. SI-x averages a lilac and two
  honeysuckles, and we compare it with lilac. Its lilac component alone has
  a bias of −0.2 days in Germany (RMSE 3.4 against 5.5). In Sweden the
  component runs 2.8 days late and is no better. The app keeps the
  published index; switching to the component would be a deviation to
  decide on.

**Sweden is weak.**
- Gothenburg 0.97, Stockholm 0.64, Malmö 0.54.
- 2008 and 2009 drive it: the model was 8 to 17 days late in Stockholm and
  Malmö. From 2010 on the correlation is 0.82 (0.67 to 0.92). The network
  was starting up in those two years (about 20 lilac records nationwide per
  year, 76 or more from 2010), so the model or the observations may be off.
  The years stay in: they were not dropped for looking bad.
- The reference is thin: a median of 3 to 4 observations per city-year,
  sometimes one.
- Sweden still shows days in the MVP (decided 2026-10-11); how to
  communicate the weaker evidence is open.

**How far this goes.**
- Cities share each year's weather (anomalies correlate 0.63 between
  cities), so the unit of evidence is the spring, not the city-year. The
  intervals resample whole years for that reason.
- Two countries. Nothing is claimed for other climate zones.
- Before 1951 the German observations are too sparse to test, so the
  1940–1950 trend values are modelled only. So is everything before 2008
  in Sweden.

**Our code is the same model as USA-NPN's.** A test in the repo
(`tests/test_si_x_matches_usanpn.py`) compares every leaf and bloom day
with USA-NPN's own code at a pinned version: identical on all 680 ERA5
city-years (8 cities, 1940–2024) and on 512 synthetic series, 7,152 days in
all. The test shows we compute what USA-NPN's map function computes; that
this function is the model of the papers rests on USA-NPN
(`docs/validation_audit.md` has the detail). Three known differences from
what USA-NPN publishes, none of them a change to the model:
- We keep the three-plant average as it comes out, with decimals. USA-NPN's
  maps store it as a whole day.
- The trigger threshold is 999.5, as in USA-NPN's code. The paper's table
  says 1000. On our data that would move the bloom index in 32 of 680
  city-years, by at most one day.
- USA-NPN feeds the model days 1–240 only. We don't cut it off; the latest
  bloom in our data is day 167.

**Published benchmark.** Izquierdo-Verdiguier & Zurita-Milla (2024),
*Scientific Data* 11, 905: SI-x bloom RMSE 7.44 days against 165,814
European lilac observations (leaf: 17.48). Not like for like, since theirs
is against single observations and ours against station medians. The
methodology page says "within about a week for a single lilac".

**Still to do before launch.**
1. Cross-check against the published 1 km SI-x grid (same paper, Europe
   1950–2020) at our cities. Not started: on 2026-10-11 the repository's
   file storage (4TU.ResearchData, one 14 GB archive) was down for
   maintenance. Licence to settle first: the 4TU record says CC BY 4.0,
   the Earth Engine community catalog's copy says CC BY-NC 4.0.

**Rules for adding a zone.**
- A new zone is claimed only after its cities pass this test against
  observations.
- If the model fails there, don't launch there, or show a categorical badge
  ("earlier / typical / later") instead of days.

**Reference data** (detail in `docs/reference_data_research.md`):
- In use: DWD, Germany (CC BY 4.0); SLU Naturens Kalender, Sweden (CC0,
  programme observers only).
- PEP725: licence per dataset since May 2026, no longer non-commercial
  only. The route to a third zone; request deferred until after the MVP.
- No open lilac data: UK, Switzerland, Czechia, the Mediterranean.

Evidence lives in `docs/bloom_multiyear.md` (generated) and
`docs/validation_audit.md` (what was claimed, what held up).

---

## 4. Infra & setup

**Repo:** one public monorepo. Today it holds `/validation` and the test
scripts; the target layout is:

```
/pipeline    → Python: CDS pull, SI-x model, results JSON, static page generation
/site        → static HTML/CSS/vanilla TS (static hosting, provider to be chosen)
/.github/workflows/daily.yml → the scheduled job
/docs, /journal → validation evidence and the build log
```

**Accounts for the MVP:**
- Copernicus CDS (done). The API token goes in a GitHub Actions secret,
  never in the repo. Accept the dataset's Terms of Use on the CDS website
  once; the API can't do it.
- Domain: `callofkiuru.eu` at Scaleway (France), bought 2026-10-15.
  European on purpose: `.eu` is run by EURid, a Belgian non-profit,
  while every `.com` pays a registry fee to Verisign (US).
- Hosting: European, to be chosen (was Cloudflare Pages). Needs a free or
  cheap tier, HTTPS on the custom domain, and to survive a share spike.
- Ko-fi for the tip button (0% fee on the free plan).

**Stack:**
- Pipeline: Python, because `cdsapi` is the recommended Copernicus client.
- Compute: GitHub Actions on a schedule. No server.
- Frontend: static HTML from Jinja2 templates, with plain JavaScript where
  interaction needs it, regenerated daily. No framework and no build step.
  Static pages give correct Open Graph tags per city, which a
  client-rendered app doesn't.

**Licensing:**
- Copernicus CDS (ERA5): CC BY 4.0, so any use with attribution.
- ECA&D and E-OBS: non-commercial research and education only. Not used.
- DWD: CC BY 4.0. SLU: CC0.
- PEP725: licence per dataset; check each one before use.

---

## 5. Frontend (MVP)

**Built (2026-10-13): the ranking, the city pages and a method page.**
`python -m pipeline.build_site` turns `data/bloom.json` into `site/dist/`:
a sortable ranking of the 8 cities, a page per city with its headline,
dates and every year since 1940, and a method page on how the 1991–2020
average is worked out and why those years. English, no design yet. This is
the only place numbers are rounded, to whole days (the averages on the
method page to one decimal).

Still to build, in order:
1. Deploy as it is on `callofkiuru.eu`: code public (MIT), data, docs and
   journal moved to a private repo first. Indexed from day one, each page
   with its canonical URL on the domain. Design then iterates on the live
   site, and going public is the build-in-public day 0.
2. Daily job (§2 step 7), which takes over the redeploys.
3. Trend chart on each city page.
4. Methodology page: the average is explained (`method/`); the validation
   evidence and its limits are still to add.
5. Share-card images and the design.

Decided:
- Plain JavaScript, not TypeScript: the only script is a table sorter, and
  TypeScript would add a build step for it.
- All cities are shown the same way. The wording for Sweden's weaker
  evidence is settled at the end.
- DWD and SLU are credited on the method page, where the lilac check is
  mentioned, in DWD's wording for processed data ("Based on data from
  Deutscher Wetterdienst"). The other pages show none of their data and
  carry the Copernicus line only.

To settle with the design:
- The difference is rounded from the unrounded value, and each date is
  rounded on its own, so the two can look a day apart: Hamburg 2026 shows
  2 May against an average of 3 May, and a difference of 0 (it is −0.4).
- The site cannot link to the validation documents while the GitHub
  repository is private (resolved by step 1).

---

## 6. After the MVP

In rough order:

1. **A third climate zone.** Request lilac data from PEP725, validate, then
   extend the claims. This is what turns "German and Swedish cities" into
   "Europe".
2. **More cities** in the validated zones.
3. **Map and location search.** Leaflet + OpenStreetMap; geocode via
   Nominatim, snap to the nearest supported city and say so ("showing the
   nearest supported location, ~12 km away").
4. **Email digest** (Brevo, EU-based) to bring people back each spring.
   Web push later; iOS support in the EU needs re-checking first.
5. **More events per year.** Leaf-out needs a different published model;
   frost dates and growing-season length reach a gardening audience.
6. **Coverage beyond a city list.** USA-NPN models a continuous grid and
   tells its story through a curated set of cities. Same pattern here: the
   model can run anywhere, the public list stays curated and validated.
7. **A 6-day forecast.** USA-NPN forecasts its spring indices 1 to 6 days
   ahead from NOAA's forecast grid (NDFD); its Alaska product states this,
   and a 2016 report says the same for the lower 48. Nothing longer. That
   they run the model unchanged on forecast temperatures is our reading of
   the product descriptions, not a documented method. Before deciding: read
   the forecast-uncertainty section of USGS OFR 2017-1003, and pick a
   European forecast source (a new data source, licence to check).
8. **"How unusual is this year."** USA-NPN's return-interval maps show how
   often a spring has been as early or late as this one. Our 1940–present
   series supports the same thing without a new model.

A database (Supabase Postgres, Frankfurt region) comes in with the first
feature that needs one: visitor data such as signups, or enough locations
to search and filter.

Two requests to send once the site is live:
- PEP725, for lilac data (item 1 above).
- USA-NPN, to add a licence to `gridded_models`. It has none, so we keep
  none of its code and only compare against it in a test.

---

## 7. Marketing & content

- Instagram and Bluesky from day one, same assets on both: per-city cards,
  rankings, the trend chart, and validation entries from the journal.
- Put the Bluesky account on a Eurosky PDS (EU-hosted), consistent with the
  open, EU-native premise.
- **Say which index.** USA-NPN maps first leaf, first bloom and a late-bloom
  index against an average over the same 1991–2020 period; we show first
  bloom only. A US "spring is
  early" figure based on first leaf is not the same measure as ours, so the
  methodology page and any comparison with US numbers must say so.
- **Positioning: peer-reviewed science, made live and local.** The model
  and a Europe-wide grid are published; what's missing is a live, per-city
  view. Check for existing live European products before using "first".

## 8. Monetization

- Ko-fi tip button. Nothing else until usage says otherwise.

## 9. Building-in-public journey log

- One dated file per entry under `/journal/`, written as things happen: a
  validation run, a bug fixed, a chart first rendering, a decision.
  `CLAUDE.md` has the format.
- Screenshots alongside the entry they belong to.
- Concise: what changed, why it matters, what's surprising. Debugging
  minutiae belong in commit messages.
