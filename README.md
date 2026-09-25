# UK Attention Atlas

The UK Attention Atlas is T&E's research and monitoring pilot for exploring how
attention moves alongside events and physical conditions. The pilot keeps news,
monitored-account social posts, polling, search interest and MODIS vegetation
observations as separate layers with explicit units and denominators.

The current release is a local, reproducible **synthetic fixture / engineering
demonstration**: formulaic GDELT-shaped news, observed-count Bluesky panel rows,
a single synthetic UK MODIS NDVI anomaly record, and GDACS/FIRMS-shaped events are
validated and exported to the React frontend. It is not evidence of UK attention or
physical conditions. Provider adapters remain available for real collection when
T&E credentials and access approvals are ready.

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

The fixture command is capped and non-billable. Real GDELT Web NGrams collection
through BigQuery is a separate command boundary and is not run by a Netlify build.
The frontend can also be built with `cd frontend && npm run build`.

Live temperature, greenness and public event collectors are documented in
[`docs/LIVE_DATA_PIPELINES.md`](docs/LIVE_DATA_PIPELINES.md). They write
reviewable, source-separated bundles under `data/live/` and never replace the
fixture release automatically.

Build and validate the real-data candidate, then open it with
`http://localhost:5173/?release=candidate`:

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
```

## Operational command boundaries

```text
validate-config       validate topics, outlet registry, account panel and geographies
audit-panels          report seed/review status and language coverage warnings
dry-run               show capped collection plan without provider calls
collect-fixture       create a deterministic local vertical-slice archive
collect-layers-fixture create source-separated price/weather/disruption fixtures
collect               provider collection entry point (credentials required)
collect-haduk-live    download and normalize Met Office country temperature
collect-modis-ndvi-live  download monthly NASA country greenness (Earthdata)
collect-gdacs-live    collect free historical GDACS event context
collect-ea-floods-live snapshot the current England Environment Agency feed
collect-firms-live     collect NASA FIRMS country-day fire detections
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
