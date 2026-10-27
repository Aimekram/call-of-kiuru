# Call of Kiuru — Build Plan

A European phenology dashboard: for each tracked city, show how many days
earlier or later spring arrived this year than in 1991–2020, modelled from
open climate data. Shareable, and honest about its own uncertainty.

"Spring" means the SI-x bloom index (first lilac bloom), shown as the
"spring bloom" (renamed from "start of spring" on 2026-10-21). DWD's
phenological calendar (phaeno_faltblatt.pdf) opens each season with a
marker phase: early spring with hazel bloom, first spring with
forsythia, full spring with apple bloom, early summer with elder bloom.
Lilac is not a marker, so checked in DWD's own observations near the 14
German cities, 1951-2024: lilac first bloom fell between apple and elder
bloom in 600 of 608 city-years (98.7%), 6 to 8 days after the apples
(Germany-wide medians 1991-2020: apple day 118, lilac 125, elder 148).
So the spring bloom marks full spring, not its start. Shown for Germany
only; the Swedish season names are not checked. USA-NPN describes its
indices as models of the "start of spring", meaning first leaf or first
bloom; for a first-bloom index in Europe that label didn't fit.

---

## 1. MVP scope (decided 2026-10-11)

**Cities: 20, each tested and graded (2026-10-20).** Germany: Freiburg,
Munich, Stuttgart, Nuremberg, Frankfurt, Cologne, Dresden, Leipzig, Hanover,
Berlin, Bremen, Hamburg, Rostock, Kiel. Sweden: Malmö, Växjö, Gothenburg,
Jönköping, Örebro, Stockholm. The first 8 launched on 2026-10-18; 12 more
added on 2026-10-20. A city is added only after it has been tested against
observations (§3, rules for adding a city).

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
`data/bloom.json` for the 20 cities: 1,740 rows, 1940–2026. A normal run
takes about 10 minutes, nearly all of it waiting for 20 small CDS requests. Tests in
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
year each network covers, nothing fitted (`bloom_multiyear.md` in the
docs repo, `run_bloom_test.py`). Correlation and error are for anomalies, which is
what the app shows; intervals are 95%.

| | Springs | Correlation | Error vs normal-year | RMSE, bias |
|---|---|---|---|---|
| Germany, 5 cities, 1951–2024 | 74 | **0.92** (0.88 to 0.94) | 3.9 vs 8.9 days | 5.5, −3.7 |
| Sweden, 3 cities, 2008–2024 | 17 | **0.69** (0.46 to 0.87) | 4.6 vs 6.4 days | 5.0, −0.3 |

**With 20 cities (2026-10-20).** Nine German and three Swedish cities
added, spread across regions, graded by the rule below:

| | Cities | City-years | Correlation | Error vs normal-year | Skill |
|---|---|---|---|---|---|
| Germany | 14 | 1036 | **0.92** (0.89 to 0.95) | 3.8 vs 8.9 days | 0.82 |
| Sweden | 6 | 99 | **0.72** (0.54 to 0.87) | 3.9 vs 5.6 days | 0.52 |

Under the current grading rule (below): all 14 German cities and
Gothenburg good; Örebro, Stockholm and Växjö fair; Jönköping and Malmö not
yet confirmed. In Sweden the result tracks the
observers: the new cities have about 8 a year, Stockholm and Malmö 3 to 4.
Swedish misses in days are like Germany's; its springs vary less, so the
correlation is lower. Bremen and Hannover run 5 to 6 days early, steadily
(drift under 0.3 days per decade), mostly the honeysuckles.

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
with USA-NPN's own code at a pinned version: identical on all 1,700 ERA5
city-years (20 cities, 1940–2024) and on 512 synthetic series, 13,272 days in
all. The test shows we compute what USA-NPN's map function computes; that
this function is the model of the papers rests on USA-NPN
(`validation_audit.md` in the docs repo has the detail). Three known differences from
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

**Rules for adding a city (decided 2026-10-20, before the new cities were
tested).** No pass mark: every city is tested and shows its result.
- A city is shown only if it can be tested: at least 10 springs with
  nearby lilac observations (same networks and search boxes as above).
- Each city gets a grade from the low end of the 95% range of its skill
  (the MSSS on anomalies, shown on the site as the "skill score", a
  decimal: how much better than guessing an average spring every year),
  resampling whole years for that city alone: **good** if the low end is
  0.5 or more (well ahead of that guess), **fair** if it is above 0 (shown
  to beat that guess), **not yet confirmed** otherwise. The low end, not
  the estimate, so a city with few springs can't look good on a lucky
  handful of years. A city that is not yet confirmed still shows its
  number: its check is inconclusive, so far from short records (16 to 17
  springs, in Sweden) with springs that vary little, not from few
  observers (Jönköping has 8.5 a year, more than Stockholm or Gothenburg),
  while the same model is confirmed in most cities; its page says so.
- Revised 2026-10-20, after the results were seen. The first rule used
  the anomaly correlation with cut-offs 0.8 and 0.5. Changed because the
  site states sizes ("8 days early"), which the correlation doesn't test
  and the skill does; because the skill (MSSS on anomalies) is a
  standard forecast-verification score (Murphy 1988, Monthly Weather
  Review 116, 2417-2424, read in full: eq. 3 defines SS = 1 − MSE(f) /
  MSE(reference), "percentage improvement in accuracy" when multiplied by
  100. Ours is his Case I, the sample mean as the reference (eq. 4),
  applied to anomalies, so of the three terms of eq. 12, r² − (r −
  s_f/s_x)² − ((f̄ − x̄)/s_x)², the last (a constant offset) is removed on
  purpose: the site compares each city with the model's own average, so
  the offset cancels there too. The amplitude term stays. He warns that
  the correlation "may lead to substantial overestimation of forecasting
  performance" (p. 2424) and shows the sample-mean reference gives the
  lowest skill of the single-valued references (p. 2421). Also used with
  climatology as the reference by the WMO Lead Centre for sub-seasonal
  forecasts) and the one the method
  page already reports per country; and because 0.8 and 0.5 had no
  meaning of their own, while 0 does (no better than climatology). The
  WMO's own long-range verification attachment (Manual on the GDPFS)
  could not be read directly: its archived copies are gone and the
  manual is sold. The cautious end and the lines at 0 and 0.5 are our
  choice, and the method page says so. The change is recorded here, not
  on the site. Grades before and after:
  unchanged for all 14 German cities and Gothenburg (strong), Örebro and
  Växjö (moderate) and Malmö (weak); Stockholm weak to moderate (low end
  0.19); Jönköping moderate to weak (low end −0.03). The same day the
  names changed to good / fair / not yet confirmed: "weak" read as a
  verdict that the model fails there, when the check is only
  inconclusive. Known limit: the
  bootstrap intervals are somewhat narrow with 16 to 17 springs, so the
  Swedish grades near a cut-off (Växjö 0.02, Jönköping −0.03) could tip
  either way.
- The grade and the numbers behind it are on the city page and
  explained on the method page; in the ranking too once built (§5).
- Fixed before the 12 new cities were run. The 8 existing cities' point
  estimates were already known, so for them the rule is not blind.

**Rules for adding a zone.**
- A new zone is claimed only after its cities are tested against
  observations, as above.
- If the model fails there, don't launch there, or show a categorical badge
  ("earlier / typical / later") instead of days.

**Reference data** (detail in `reference_data_research.md`, docs repo):
- In use: DWD, Germany (CC BY 4.0); SLU Naturens Kalender, Sweden (CC0,
  programme observers only).
- A lilac "first bloom" after 31 August is left out, in both networks
  (2026-10-20). It removes one record of 164,749: SLU 2008 near Örebro, day
  273, filed with the observer's autumn records after their own spring
  bloom records. Under the first grading rule, without it Örebro was weak
  (−0.18), with it moderate (0.81).
- PEP725: licence per dataset since May 2026, no longer non-commercial
  only. The route to a third zone; request deferred until after the MVP.
- No open lilac data: UK, Switzerland, Czechia, the Mediterranean.

Evidence lives in the private docs repo (`../call-of-kiuru-docs/docs/`):
`bloom_multiyear.md` (generated) and `validation_audit.md` (what was
claimed, what held up).

---

## 4. Infra & setup

**Repo:** one public monorepo. Today it holds `/validation` and the test
scripts; the target layout is:

```
/pipeline    → Python: CDS pull, SI-x model, results JSON, static page generation
/site        → static HTML/CSS/vanilla TS (static hosting, provider to be chosen)
/.github/workflows/daily.yml → the scheduled job
```

`docs/` (validation evidence) and `journal/` (the build log) are in a
private sibling repo, `call-of-kiuru-docs`.

**Accounts for the MVP:**
- Copernicus CDS (done). The API token goes in a GitHub Actions secret,
  never in the repo. Accept the dataset's Terms of Use on the CDS website
  once; the API can't do it.
- Domain: `callofkiuru.eu` at Scaleway (France), bought 2026-10-15.
  European on purpose: `.eu` is run by EURid, a Belgian non-profit,
  while every `.com` pays a registry fee to Verisign (US).
- Hosting: GitHub Pages to start (2026-10-18), deployed by
  `.github/workflows/pages.yml`. Free, HTTPS on the custom domain, a soft
  limit of 100 GB a month. The repo and the job are on GitHub already. It
  is US-owned (Microsoft), so a European host is still the aim; the site
  is static files, so moving means a new deploy step and a DNS change.
- Suppi (suppi.pl/devtortie) for the tip link, chosen 2026-10-18. Polish:
  Crowd8 sp. z o.o., Warsaw, the company behind Patronite; payments via
  Autopay. No commission on tips by its own account (it asks supporters for
  an optional extra). Checkout in Polish and PLN, so the link says "card, in
  PLN". Considered: buycoffee.to (about 10% in fees), Ko-fi (0%, but UK and
  Stripe/PayPal), Tipeee (FR, 8%), Liberapay (FR, recurring-first), Mollie
  (NL payment link). A plain footer link, not a widget: nothing loads from
  Suppi until clicked.
- GoatCounter for visit counts (2026-10-18), site `callofkiuru` on the
  `aimekram` account. No cookies, no stored IPs, run from Ireland with
  data in Finland and Germany. `count.js` (ISC) is served from our own
  `static/`, copied from gc.zgo.at, so no outside script loads; recopy it
  for updates. Localhost is not counted.

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
a sortable ranking of the cities, a page per city with its headline,
dates and every year since 1940, and a method page on how the 1991–2020
average is worked out and why those years. English, no design yet. This is
the only place numbers are rounded, to whole days (the averages on the
method page to one decimal).

**Live (2026-10-18) on `callofkiuru.eu`**, as it is: code (MIT) and data
public, docs and journal in a private repo. Indexed from day one, each
page with its canonical URL on the domain, all listed in `sitemap.xml`
(2026-10-20, written by the build with `robots.txt`; no `<lastmod>`, which
would be wrong whenever the code changes a page and the data doesn't).
A custom `404.html` (2026-10-20): "Spring came 404 days late", with a lilac
sprig that blooms from the bottom up; not indexed, links from the root.
Design iterates on the live site, and going public is the build-in-public
day 0. HTTPS works, and plain HTTP redirects to it (checked 2026-10-20).

**Design (2026-10-18): "Meadow"**, chosen from three directions in
`design/directions.html`. Cream paper, near-black ink, cards with a hard
offset shadow, after query.gg. Fraunces for headings, Outfit for text,
Bricolage Grotesque Bold for the name next to the logo (cut down to its
letters, `design/wordmark.html`), all under the SIL Open Font License and
served from the site, not Google.
Colours in `site/static/style.css`, with light and dark mode from
`light-dark()`. Early is ochre and late is blue, a warm spring against a
cold one, so neither reads as good or bad. Pink against blue was dropped
because it read as an alarm. Lilac against blue fails for red-green
colourblind readers. The logo (`design/logo-bold.html`, X2) is a small
Meadow card with waves spreading from a lilac sprig in its corner; it is
the header logo, the share cards' brand and the avatar
(`design/avatar.svg`). At tab size the sprig becomes a dot (Y): the
favicon.

Still to build, in order (reordered 2026-10-18: until spring the history is
what people see, so the interface comes before the daily job):
1. Trend chart on each city page. Built 2026-10-18: a bar per year since
   1940, earlier below the line in ochre, later above in blue, all cities
   on one scale (±30 days) so they compare. Bars show whole days like the
   table. A box in the plot's top corner shows the newest year; hover or
   the arrow keys switch it to any other. SVG made at build time, so the
   share cards can reuse it. A ±25 scale was considered and dropped: it
   would cut 7 bars, Cologne's −26 in 2024 among them.
2. Share-card images, for posts on Instagram and Bluesky. Built 2026-10-18:
   `pipeline/share_cards.py` renders a card per city (headline and trend
   chart), one for the ranking and one for the other pages, from
   `templates/card.html` in the site's light theme, photographed by headless
   Chrome at 1200×630 into `cards/`. Every page's og:image and
   twitter:card point at its card; the deploy runs the step after the build.
   The same cards in Instagram's 4:5 portrait (1080×1350, a larger chart
   with "Every spring since 1940") go to `cards/instagram/`, published with
   the site so the current ones can be posted from a phone.
   Later (decided 2026-10-18 to wait): a "Share" button on city pages and
   the ranking. The phone's own share sheet (Web Share API), copying the
   link on desktop, no third-party scripts, clicks counted in GoatCounter.
   Optionally share the Instagram image itself on phones. Until then,
   sharing happens through the account's own posts.
3. Methodology page (`method/`): "why a model", the average, and (2026-10-18)
   the validation by country (correlation, typical miss against calling
   every spring normal, skill, 95% ranges, from `bloom_multiyear.md`), the
   lilac-only offset, limits, and why only Germany and Sweden. DWD and SLU
   are credited there. Per city, a small chart of modelled against observed
   bloom by year (built 2026-10-19, from `data/bloom_multiyear.csv`, now
   committed): two lines on real dates, later higher, observed in ink and
   the model in green, one date scale for all cities and one year range per
   country. Dates, not days from average, so the page has one "average"
   only; the offset shows as a gap, explained just above. No observed
   column on city pages for now: it would be mostly empty and show the
   offset in every row.
4. Daily job (§2 step 7), which takes over the redeploys. Needed by the end
   of February 2027: the earliest modelled bloom in the test is late March
   (Cologne 2024), and the job wants a few weeks on live data first.

Decided:
- Plain JavaScript, not TypeScript: the only script is a table sorter, and
  TypeScript would add a build step for it.
- All cities are shown the same way. The wording for Sweden's weaker
  evidence is settled at the end.
- Differences are worked out from the unrounded days, and each date is
  rounded on its own, so the two can look a day apart: Hamburg 2026 shows
  2 May against an average of 3 May, and a difference of 0 (it is −0.4).
  This happens in 185 of the 696 city-years. Kept as it is (2026-10-18):
  the ranking's column says "Average date, rounded", city pages say
  "around", and the notes under the tables explain it.
- The validation documents stay in the private docs repo, so the method
  page carries the evidence itself (done 2026-10-18, step 3).
- DWD and SLU are credited on the method page, where the lilac check is
  mentioned, in DWD's wording for processed data ("Based on data from
  Deutscher Wetterdienst"). The other pages show none of their data and
  carry the Copernicus line only.

Next round of site improvements (decided 2026-10-20, kept separate from
adding the 12 cities):
- A quality block on each city page from `data/bloom_grades.csv`. Built
  2026-10-20: a "Track record" row in the facts (signal bars and the
  grade, linking down), and a section "How well the model does here":
  springs checked, observations a year, how many days off the model and
  the average-spring guess typically were, the skill score (a decimal: 1
  perfect, 0 no better than the guess; not a percentage, which read as a
  share of days) with its 95% range, the typical miss
  against calling every spring normal, a range chart of the skill on a
  −0.5 to 1 scale with the not yet confirmed / fair / good zones (the low end
  marked, since it sets the grade), and why the city got its grade. Ink
  only, since colour already means early and late.
  The method page explains the grades (`#grades`): the rule in plain
  words, the 10-spring floor, which cities have which grade today
  (generated from the data), and the source of the score; the lines are
  stated as our choice. Each of its city charts carries the grade in its
  caption. Its wording now
  matches the city pages ("guessing an average spring every year").
- The grade in the ranking.
- Split the method page (2026-10-27): "How it works" (`method/`: why a
  model, why only Germany and Sweden, the average) for the curious
  visitor, and "How well the model does" (`accuracy/`: the by-country
  table, the grades and the 10-spring floor, the 20 city charts, the
  limitations, the data and the code) for the skeptic. The method page was
  about 6,100px tall on desktop with 20 charts.
- Two AI lines (2026-10-27), no commentary on AI companies: in "How it
  works", that no AI produces the dates (SI-x is a fixed set of published
  equations, and our code gives exactly USA-NPN's days); in "How well the
  model does", that the code was written with AI assistance, checked
  against USA-NPN's code and observed bloom, and open with its tests.

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
   series supports the same thing without a new model. Built 2026-10-19:
   on city pages, a row in the facts under the headline, e.g. Malmö
   "Springs 1940–2025: 15 of 86 came earlier than 2026, 1 on the same day
   of the year" ("than 2026" added 2026-10-20: without it, a cold reader,
   Mistral, took the range for an off-by-one). Not next to the chart: the bars measure against the 1991–2020
   average, this ranks against every past spring, and both say "earlier".
   Unrounded days; the rarer side
   (earlier or later) is counted, with no adjectives. Ties are common (the
   index comes in thirds of a day: 230 of 696 values repeat within a city)
   and are said separately. No line before bloom.

A database (Supabase Postgres, Frankfurt region) comes in with the first
feature that needs one: visitor data such as signups, or enough locations
to search and filter.

Two requests, sent last (decided 2026-10-18): first see how people react
to the 8 cities, and whether anyone asks for more. Item 1 waits on the
first.
- PEP725, for lilac data (item 1 above).
- USA-NPN, to add a licence to `gridded_models`. It has none, so we keep
  none of its code and only compare against it in a test.

---

## 7. Marketing & content

- Instagram and Bluesky from day one, with different jobs (decided
  2026-10-20): Bluesky for the work in progress (validation entries and
  decisions from the journal), Instagram for results (per-city cards,
  rankings, the trend chart).
- **About page** (`about/`, 2026-10-20): what the site is, where it comes
  from (USA-NPN's spring maps, same model and average, for Europe), the name
  (*kiuru* is the skylark; the Finnish saying "kuu kiurusta kesään", and
  Luontoliitto on warming moving the birds' arrival earlier), and where the
  build is shared: Bluesky @callofkiuru.eu for the work in progress,
  Instagram @callofkiuru for results. Linked from every footer; the link
  for bios.
- The Bluesky account is on a Eurosky PDS (eurosky.social, EU-hosted),
  consistent with the open, EU-native premise (done; per its PLC record,
  checked 2026-10-20).
- **Say which index.** USA-NPN maps first leaf, first bloom and a late-bloom
  index against an average over the same 1991–2020 period; we show first
  bloom only. A US "spring is
  early" figure based on first leaf is not the same measure as ours, so the
  methodology page and any comparison with US numbers must say so.
- **Positioning: peer-reviewed science, made live and local.** The model
  and a Europe-wide grid are published; what's missing is a live, per-city
  view. Check for existing live European products before using "first".

## 8. Monetization

- Suppi tip link. Nothing else until usage says otherwise.

## 9. Building-in-public journey log

- One dated file per entry under `journal/` in the private docs repo,
  written as things happen: a
  validation run, a bug fixed, a chart first rendering, a decision.
  `CLAUDE.md` has the format.
- Screenshots alongside the entry they belong to.
- Concise: what changed, why it matters, what's surprising. Debugging
  minutiae belong in commit messages.
