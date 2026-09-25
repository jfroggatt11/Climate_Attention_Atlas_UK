# Live data pipelines

The repository now has four source-separated collectors. Each writes a JSON
bundle under `data/live/<source>/`, keeps raw responses or source files under a
`raw/` directory, and records a hash, retrieval time, endpoint, and coverage
notes in `source_snapshot`. Live bundles are candidates for review; they do not
replace the checked-in fixture release automatically.

## Temperature: HadUK-Grid

HadUK-Grid is the Met Office's open-government-licence UK land observation
dataset. The collector downloads one annual country-area NetCDF file and emits
monthly `tas` observations in degrees Celsius:

```bash
uv sync --extra live
uv run uk-atlas collect-haduk-live
```

The collector discovers the latest versioned country-area file through CEDA's
JSON directory listing. CEDA requires a free registered account and may require
an archive access token; put that token in `CEDA_ACCESS_TOKEN`. The `--url` and
`--input` options remain available for a pinned archive or an offline run.

The Met Office publishes provisional recent files which can later be revised.
Use `--url` when a release uses a different archive URL.

## Greenness: NASA MOD13C2

The MODIS collector discovers monthly MOD13C2 v061 granules, downloads only the
NDVI variable, and computes latitude-area-weighted UK country means over valid
0.05-degree cells. It requires a free NASA Earthdata Login. If the boundary
path does not exist, the collector downloads and caches Natural Earth's public
sovereign-country GeoJSON:

```bash
export EARTHDATA_TOKEN='…'  # or EARTHDATA_USERNAME/PASSWORD
uv run uk-atlas collect-modis-ndvi-live \
  --start 2025-01-01 --end 2025-12-31 \
  --boundary-geojson data/live/boundaries/ne_10m_admin_0_countries.geojson
```

Credentials are read from the environment or the ignored project `.env` file
and never written to the bundle.

FIRMS accepts either `NASA_FIRMS_API_KEY` (the name used in this project's
`.env.example`) or the provider's `FIRMS_MAP_KEY` name.

```bash
uv run uk-atlas collect-firms-live --start 2025-01-01 --end 2025-01-07
```

## Free event context

GDACS needs no key and supports historical date ranges:

```bash
uv run uk-atlas collect-gdacs-live --start 2025-01-01 --end 2025-12-31
```

The Environment Agency collector captures the current England warning/alert
feed. It is explicitly a snapshot and cannot be used as historical daily
backfill:

```bash
uv run uk-atlas collect-ea-floods-live
```

## Climate completion: burned area

The old Wildfire-Trends implementation is retained in `satellite.py`. The
Atlas now exposes the MCD64A1 Burn_Date path through AppEEARS. It uses the
Earthdata username/password, submits a bounded UK task, keeps the task ID and
native rasters under the ignored live directory, and emits daily hectares:

```bash
uv run uk-atlas collect-modis-burned-area-live \
  --start 2025-01-01 --end 2025-12-31 \
  --boundary-geojson data/live/boundaries/ne_10m_admin_0_countries.geojson
```

Burned area is separate from NDVI, FIRMS detections and GDACS events.

## Economic context

The no-key public feeds can be refreshed together:

```bash
uv run uk-atlas collect-economics-live \
  --start 2025-01-01 --end 2026-09-25 \
  --symbols TSLA BP.L SHEL.L
```

This collects official DESNZ weekly pump prices, ONS CPI, FRED Brent spot
prices, and exploratory daily closes for Tesla, BP and Shell. The stock adapter
is kept as market context and must be checked for redistribution terms before
publication. It does not imply that company prices measure public attention.

## Review before release

Inspect the bundle and snapshot first, then transform approved records into the
normal release tables. A successful collector run alone does not make the data
publishable: country coverage, revisions, and source terms still need review.

## Candidate release

After the source bundles are refreshed, assemble the physical-context candidate:

```bash
uv run uk-atlas build-live-candidate
uv run uk-atlas validate-live-candidate
```

The candidate is the frontend default. Add `?release=candidate` explicitly if
needed; add `?release=fixture` to view the synthetic interface fixture. It
contains real temperature, raw NDVI, MCD64, FIRMS, GDACS and economic snapshots,
but the browser does not refresh them. News and Bluesky are empty in this
candidate until their live collection and denominator review is complete.
