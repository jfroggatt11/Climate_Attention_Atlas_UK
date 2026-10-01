# Live data pipelines

The repository now has four source-separated collectors. Each writes a JSON
bundle under `data/live/<source>/`, keeps raw responses or source files under a
`raw/` directory, and records a hash, retrieval time, endpoint, and coverage
notes in `source_snapshot`. Live bundles are candidates for review; they do not
replace the checked-in fixture release automatically.

## Political communication: UK MP social posts

The MP importer reads the `engagement` tab exported from Google Sheets or XLSX.
It uses the day-grain `posts` field only and ignores likes, shares, comments and
views. It maps `climate_change`, `evs`, `fuel_prices` and `extreme_weather` to
the atlas topic IDs, aggregates party/platform rows to UK topic-day totals, and
checks those totals against the month and year control rows.

```bash
uv run uk-atlas import-mp-social \
  --input /path/to/social_media_uk_mp.xlsx \
  --output data/live/junkipedia_mp/bundle.json \
  --release-id uk-atlas-candidate-2025-01-01-2025-12-31 \
  --run-id junkipedia-mp-2026-09-30
```

The resulting series measure classified MP communication volume, not enacted
policy. The source notes describe a candidate set and weekly classification
rebuild, so the release must retain classifier and coverage notes until a more
sophisticated event-discourse method is introduced.

### Google Sheets credentials

For a private Sheet, use a read-only service account for the scheduled
collector:

1. Create or select a Google Cloud project and enable the Google Sheets API.
2. Create a service account. Do not grant it broad project roles.
3. Copy its email address and share only the MP Sheet with that address as
   **Viewer**. Google Cloud IAM permissions alone do not grant access to a
   Sheet.
4. Create a JSON service-account key for local testing and store it outside the
   repository. For a hosted scheduler, use the platform secret store or
   workload identity federation instead of committing the key.
5. Set `GOOGLE_APPLICATION_CREDENTIALS` to the key path and pass the Sheet ID
   from the URL (`/spreadsheets/d/<SHEET_ID>/edit`) to the importer.

The importer requests `engagement!A:O` with unformatted values and read-only
scope, so numeric post counts remain numeric and the Sheet is never modified.

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

Each live row retains the raw NDVI and adds a greenness anomaly against the
matching calendar month in the UK 2001–2020 MODIS baseline carried forward from
the old Wildfire-Trends pipeline. The candidate release stores both measures:
`ndvi` (index) and `ndvi_anomaly` (index anomaly), including baseline years,
valid-area coverage and standardized anomaly metadata.

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
contains real temperature, raw NDVI, greenness anomaly, MCD64, FIRMS, GDACS,
economic snapshots and, when imported, classified UK MP post counts. The browser
does not refresh them. News and Bluesky remain empty until their live collection
and denominator review is complete.
