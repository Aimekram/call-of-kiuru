# Call of Kiuru

A dashboard that shows, for each tracked city, how many days earlier or
later the modelled spring bloom is this year than the model's own
1991–2020 average for that city: https://callofkiuru.eu. It covers cities
in Germany and Sweden, each tested against observed lilac bloom first (the
list is in `pipeline/locations.json`).

"Spring bloom" here is a published model, not an observation: the Extended
Spring Indices (SI-x) first-bloom index, computed from open temperature data
(Copernicus ERA5). It falls in full spring as Germany's weather service (DWD)
defines it, which starts with apple bloom, after early and first spring: not
the start of spring.

The USA National Phenology Network maps the same kind of comparison for the
United States, over the same 1991–2020 period. It maps first leaf, first
bloom and a late-bloom index. We use first bloom only, because the
first-leaf index did poorly against European observations: about 13 days
early on average in the 2024 paper cited below (RMSE 17.5 days, 1,227
observations, against 7.4 days for first bloom), and weeks early in our own
check, which covers one year and few observations. A US "spring is early"
figure based on first leaf is therefore not the same measure as ours.

## What has been checked

The model is compared with observed first bloom of common lilac near each
city, for every year the open records cover. Nothing is fitted. The
correlation is for "early or late compared with the city's usual date",
which is what the dashboard shows. Last run 2026-10-20:

| | Springs | Correlation (95% interval) | Error vs always predicting a normal year |
|---|---|---|---|
| Germany, 14 cities, 1951–2024 | 74 | 0.92 (0.89 to 0.95) | 3.8 vs 8.9 days |
| Sweden, 6 cities, 2008–2024 | 17 | 0.72 (0.54 to 0.87) | 3.9 vs 5.6 days |

Our implementation gives the same leaf and bloom days as USA-NPN's code on
all 13,272 days compared (1,700 city-years of ERA5 data and 512 synthetic
series; 2026-10-20).

Limits:

- Two countries only. Nothing is claimed for other climate zones.
- The Swedish result is weaker and rests on fewer observations: a median
  of 3 to 8.5 per city and year, against 19 to 65.5 in Germany.
- SI-x averages three plant models (a lilac and two honeysuckles). The
  observations are lilac only, and of common lilac, not the cloned lilac
  that USA-NPN's documentation names for the model.
- The implementation test shows agreement with USA-NPN's code, not with the
  papers that define the model.

The results by country, with their limitations, are on the site's
[method page](https://callofkiuru.eu/method/). The full report and an audit
of what was claimed, what held up and what is still unverified are kept in
a private repository for now.

## Run it

Python 3.12 is used.

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Check the implementation** (about 15 seconds, no account needed):

```bash
python -m unittest
```

The comparison on synthetic series always runs. The comparison on ERA5 data
runs for the cities whose ERA5 download is present and is skipped otherwise.

**Rerun the validation.** This needs a free
[Copernicus CDS](https://cds.climate.copernicus.eu/) account:

1. Put your token in `~/.cdsapirc`:

   ```
   url: https://cds.climate.copernicus.eu/api
   key: <your token>
   ```

2. On the CDS website, accept the terms of use of the dataset
   `reanalysis-era5-single-levels-timeseries`. The API cannot do this for
   you.

3. Run:

   ```bash
   python run_bloom_test.py
   ```

   It downloads the lilac observations (about 60 MB) and ERA5 temperatures
   for each city (about 5 MB and 90 seconds each), then writes
   `data/bloom_multiyear.csv` (committed: the method page draws it) and a
   report, `bloom_multiyear.md`, into `../call-of-kiuru-docs/docs/` (the
   private docs repo, if you have it).

**Draw the charts** from that result:

```bash
python plot_bloom_test.py anomalies.png
python plot_bloom_test.py uncertainty.png --chart uncertainty
```

**Update the numbers** (about 30 seconds per city, needs the Copernicus account):

```bash
python -m pipeline.run
```

It downloads temperatures from January 2025 to today for each city and
rewrites `data/bloom.json`. Add `--rebuild` to recompute every year since
1940, or `--offline` to use the downloads already on disk. `python -m pipeline.check_recent` compares the years after 2024 with
German lilac observations.

**Build the site** from those numbers and look at it:

```bash
python -m pipeline.build_site
python -m pipeline.share_cards     # optional: the share images, needs Chrome
python -m http.server --directory site/dist
```

Then open http://localhost:8000. Opening the files directly does not work:
the links point at folders, which only a server resolves.

**Regenerate the USA-NPN reference** (about 5 minutes, needs network):

```bash
python -m tests.make_usanpn_reference
```

## Repository layout

```
pipeline/
  run.py                 builds data/bloom.json: bloom day per city and year,
                         the 1991–2020 average, and this year's difference
  locations.json         the cities
  era5.py, bloom.py      temperature loading and the calculation
  check_recent.py        years after the validation period vs observations
  build_site.py          turns data/bloom.json into the static site, and
                         data/bloom_multiyear.csv into the method page's charts
  share_cards.py         share images via Chrome: link previews and Instagram posts
site/
  templates/, static/    page templates, stylesheet, table sorter
  dist/                  the built site (not in the repository)
run_bloom_test.py        the validation: model vs observed lilac bloom
plot_bloom_test.py       charts of the result
validation/
  si_x_model.py          the SI-x leaf and bloom models
  cds_fetch.py           ERA5 download
  reference_fetch.py     lilac observations from DWD and SLU
  bloom_stats.py         confidence intervals, per-country and per-period results
  config.py              cities and paths
tests/
  test_si_x_matches_usanpn.py   our model vs USA-NPN's code
  test_pipeline.py              the pipeline's output vs the same reference
  make_usanpn_reference.py      produces the reference days in tests/fixtures/
data/bloom.json          the pipeline's output
data/                    downloads and working files (not in the repository)
.github/workflows/
  pages.yml              builds the site and share cards, deploys to GitHub Pages
```

`run_validation.py`, `validation/validator.py` and `VALIDATION_LOG.md` are
from the first, single-year check of September 2026. They are kept for the
record and are not part of the current workflow.

## Data sources and licences

| Source | Used for | Licence |
|---|---|---|
| [ERA5](https://cds.climate.copernicus.eu/), Copernicus Climate Change Service | Temperature | CC BY 4.0 |
| [DWD](https://opendata.dwd.de/), Germany | Lilac observations | CC BY 4.0 |
| [SLU Naturens Kalender](https://researchdata.se/en/catalogue/dataset/2022-86-1), Sweden | Lilac observations | CC0 |

Results here contain modified Copernicus Climate Change Service information.

Not used: E-OBS and ECA&D (non-commercial use only). PEP725 sets a licence
per dataset since May 2026; none of its data is used yet.

USA-NPN's [gridded_models](https://github.com/usa-npn/gridded_models)
repository has no licence, so none of its code is in this repository. The
test downloads it at a pinned version, runs it, and keeps only the
resulting days.

The code in this repository is MIT-licensed (`LICENSE`).

## References

- Schwartz, M. D., Ault, T. R., & Betancourt, J. L. (2013). Spring onset
  variations and trends in the continental United States: past and regional
  assessment using temperature-based indices. *International Journal of
  Climatology*, 33(13), 2917–2922. https://doi.org/10.1002/joc.3625
- Crimmins, T. M., and others (2017). *USA National Phenology Network
  gridded products documentation*. USGS Open-File Report 2017–1003.
  https://doi.org/10.3133/ofr20171003
- Izquierdo-Verdiguier, E., & Zurita-Milla, R. (2024). A multi-decadal 1 km
  gridded database of continental-scale spring onset products. *Scientific
  Data*, 11, 905. https://www.nature.com/articles/s41597-024-03710-5
