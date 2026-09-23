# UK Attention Atlas

The UK Attention Atlas is T&E's research and monitoring pilot for exploring how
attention moves alongside events and physical conditions. The pilot keeps news,
monitored-account social posts, search interest and MODIS vegetation observations
as separate measures with explicit units and denominators.

The first reliable vertical slice is local and reproducible: a capped GDELT-shaped
fixture, a monitored Bluesky panel fixture, refreshed UK MODIS NDVI anomaly records,
and one GDACS/FIRMS-style event layer are validated, aggregated and exported to the
React frontend. The provider adapters copied from the MVP remain available for
real collection when T&E credentials and access approvals are ready.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uk-atlas validate-config
.venv/bin/uk-atlas collect-fixture --output data/fixtures/vertical-slice.json
.venv/bin/uk-atlas export-frontend --input data/fixtures/vertical-slice.json
cd frontend && npm install && npm run dev
```

The fixture command is capped and non-billable. Real GDELT Web NGrams collection
through BigQuery is a separate command boundary and is not run by a Netlify build.
The frontend can also be built with `cd frontend && npm run build`.

## Operational command boundaries

```text
validate-config       validate topics, outlet registry, account panel and geographies
dry-run               show capped collection plan without provider calls
collect-fixture       create a deterministic local vertical-slice archive
collect               provider collection entry point (credentials required)
aggregate             validate and materialise prepared serving aggregates
check-quality         check completeness, duplicates, denominators and source status
sync-supabase         stage prepared rows; requires SUPABASE_DATABASE_URL to apply
export-frontend       export a release asset consumed by the browser
release-verify        verify release ID, hashes and frontend asset contract
runs inspect|retry    inspect or resume durable run state
```

See [STATUS.md](STATUS.md), [PLAN.md](PLAN.md), [docs/operations.md](docs/operations.md),
and [docs/data-dictionary.md](docs/data-dictionary.md) for handover details. The
frontend deliberately labels the GDELT denominator as captured GDELT UK news and
the social denominator as posts from monitored Bluesky accounts. “Attention” is
not one undifferentiated scale, and the pilot makes no causal claim.

## Repository rules

Small deterministic fixtures are checked in for smoke tests. Credentials, `.env`
files, source caches, generated research archives and provider responses are not.
The `Wildfire-Trends` repository is a read-only reference and is not modified.
