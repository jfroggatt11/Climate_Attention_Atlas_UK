# UK Attention Atlas

The UK Attention Atlas is T&E's research and monitoring pilot for exploring how
attention moves alongside events and physical conditions. The pilot keeps news,
monitored-account social posts, polling, search interest and MODIS vegetation
observations as separate layers with explicit units and denominators.

The published layer hierarchy has three top-level groups: **External events and
conditions** (Climate, Energy markets and Events), **Attention and public attitudes**
(News, Search, Social and Polling), and **Secondary impacts and responses**
(Economic, Political and Disruption). Events remain X-axis markers; observed series
from the other categories can be assigned to chart axes when available.

The checked-in fixture remains a local, reproducible **synthetic fixture / engineering
demonstration** for interface tests. The browser defaults to a separate candidate
release assembled from real temperature, MODIS raw NDVI and greenness anomalies,
MCD64 burned area, FIRMS, GDACS and economic snapshots. News and Bluesky attention
remain empty in that candidate until their live collection and denominator review is
complete.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uk-atlas validate-config
.venv/bin/uk-atlas audit-panels
.venv/bin/uk-atlas collect-fixture --output data/fixtures/vertical-slice.json
.venv/bin/uk-atlas collect-layers-fixture --output data/fixtures/data-layers.json
.venv/bin/uk-atlas validate-release --input data/fixtures/vertical-slice.json
.venv/bin/uk-atlas export-frontend --input data/fixtures/vertical-slice.json
.venv/bin/uk-atlas release-verify
cd frontend && npm install && npm run dev
```

The article-level GDELT pilot is run separately from the frontend fixture:

```bash
.venv/bin/uk-atlas estimate-gdelt-articles --start 2026-08-01 --end 2026-08-07 \
  --billing-project "$GCP_PROJECT" --max-bytes 100000000000
.venv/bin/uk-atlas collect-gdelt-articles --start 2026-08-01 --end 2026-08-07 \
  --billing-project "$GCP_PROJECT" --max-bytes 100000000000 \
  --max-total-bytes 500000000000 --run-id gdelt-2026-08-01
.venv/bin/uk-atlas validate-gdelt-article-release \
  --input data/processed/gdelt-article-release-gdelt-2026-08-01.json
.venv/bin/uk-atlas prepare-gdelt-article-serving \
  --input data/processed/gdelt-article-release-gdelt-2026-08-01.json \
  --output data/processed/gdelt-article-serving.json
```

Collection requires Google Application Default Credentials and a reviewed outlet
registry. It writes a candidate bundle and never publishes automatically. Use
`sample-gdelt-validation` to create the human review template before release.

The fixture command is capped and non-billable. Real GDELT Web NGrams collection
through BigQuery is a separate command boundary and is not run by a Netlify build.
The frontend can also be built with `cd frontend && npm run build`.

Live temperature, greenness and public event collectors are documented in
[`docs/LIVE_DATA_PIPELINES.md`](docs/LIVE_DATA_PIPELINES.md). They write
reviewable, source-separated bundles under `data/live/` and never replace the
fixture release automatically.

Build and validate the real-data candidate, then open the app. The browser now
uses the candidate by default; add `?release=fixture` when you explicitly want
the synthetic interface fixture:

```bash
.venv/bin/uk-atlas build-live-candidate
.venv/bin/uk-atlas validate-live-candidate
cd frontend && npm run dev
```

```bash
.venv/bin/uk-atlas collect-haduk-live
.venv/bin/uk-atlas collect-gdacs-live --start 2025-01-01 --end 2025-12-31
.venv/bin/uk-atlas collect-ea-floods-live
.venv/bin/uk-atlas collect-firms-live --start 2025-01-01 --end 2025-01-07
# MODIS requires an Earthdata token and a sovereign-country GeoJSON:
.venv/bin/uk-atlas collect-modis-ndvi-live --start 2025-01-01 --end 2025-12-31 \
  --boundary-geojson data/live/boundaries/ne_10m_admin_0_countries.geojson
.venv/bin/uk-atlas collect-modis-burned-area-live --start 2025-01-01 --end 2025-12-31 \
  --boundary-geojson data/live/boundaries/ne_10m_admin_0_countries.geojson
.venv/bin/uk-atlas collect-economics-live --start 2025-01-01 --end 2026-09-25 \
  --symbols TSLA BP.L SHEL.L
```

## Operational command boundaries

```text
validate-config       validate topics, outlet registry, account panel and geographies
audit-panels          report seed/review status and language coverage warnings
dry-run               show capped collection plan without provider calls
estimate-gdelt-articles  dry-run GAL, Web NGrams and GKG article query shapes
collect-gdelt-articles   collect resumable article inventory and tagging bundle
validate-gdelt-article-release validate article-level provenance and arithmetic
prepare-gdelt-article-serving prepare validated read-only article payload
sample-gdelt-validation   create a reproducible human-review sample
inspect-gdelt-article-run inspect article-pipeline stage checkpoints
collect-fixture       create a deterministic local vertical-slice archive
collect-layers-fixture create source-separated price/weather/disruption fixtures
collect               provider collection entry point (credentials required)
collect-haduk-live    download and normalize Met Office country temperature
collect-modis-ndvi-live  download monthly NASA country greenness (Earthdata)
collect-modis-burned-area-live  collect NASA MCD64 burned area via AppEEARS
collect-gdacs-live    collect free historical GDACS event context
collect-ea-floods-live snapshot the current England Environment Agency feed
collect-firms-live     collect NASA FIRMS country-day fire detections
collect-desnz-live     collect official weekly road fuel prices
collect-ons-cpi-live   collect official ONS CPI time series
collect-brent-live     collect public FRED Brent spot prices
collect-market-live    collect exploratory Tesla/BP/Shell closes
collect-economics-live collect the economic bundle together
import-mp-social      import classified UK MP post counts from Google Sheets or XLSX
aggregate             validate and materialise prepared serving aggregates
check-quality         check completeness, duplicates, denominators and source status
check-layers          check source-layer duplicates and snapshot coverage
export-layer-parquet  write the versioned source-observation Parquet archive
validate-release      check cross-table release IDs and aligned denominators
sync-supabase         stage prepared rows; requires SUPABASE_DATABASE_URL to apply
export-frontend       export a release asset consumed by the browser
release-verify        verify release status, hashes, row counts, files and frontend asset
runs inspect|retry    inspect or resume durable run state
```

See [STATUS.md](STATUS.md), [PLAN.md](PLAN.md), [docs/LIVE_DATA_ONRAMP.md](docs/LIVE_DATA_ONRAMP.md), [docs/operations.md](docs/operations.md),
and [docs/data-dictionary.md](docs/data-dictionary.md) for handover details. The
Bluesky measurement choices are documented in [docs/BLUESKY_PANEL_OPTIONS.md](docs/BLUESKY_PANEL_OPTIONS.md).
frontend deliberately labels the GDELT denominator as captured GDELT UK news and
the social denominator as posts from monitored Bluesky accounts. “Attention” is
not one undifferentiated scale, and the pilot makes no causal claim.

## Repository rules

Small deterministic fixtures are checked in for smoke tests. Credentials, `.env`
files, source caches, generated research archives and provider responses are not.
The `Wildfire-Trends` repository is a read-only reference and is not modified.
