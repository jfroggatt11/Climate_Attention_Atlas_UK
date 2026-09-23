# Build status

- **Current milestone:** 6 — source-layer expansion
- **Last completed:** source registry and contracts for prices, weather, hazards,
  disruption, markets, FIRMS/MODIS extensions, access-pending layers, provider
  request plans, unit checks and atomic Parquet export
- **Verification commands:**
  - `.venv/bin/uk-atlas validate-config`
  - `.venv/bin/uk-atlas audit-panels`
  - `.venv/bin/uk-atlas collect-fixture --output data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas collect-layers-fixture --output data/fixtures/data-layers.json`
  - `.venv/bin/uk-atlas check-quality --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas check-layers --input data/fixtures/data-layers.json`
  - `.venv/bin/uk-atlas validate-release --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas export-frontend --input data/fixtures/vertical-slice.json`
  - `cd frontend && npm test && npm run build`
- **Latest verification:** source-layer fixture contains 335 observations across 11
  registered sources; 42 Python tests pass; frontend test and production
  build passed; `audit-panels` reports expected draft-language, Welsh-coverage and
  seed-panel warnings; `validate-release` passes.
- **Known issues:** GDELT BigQuery, official Google Trends, production Bluesky
  Jetstream, DESNZ/ONS/HadUK-Grid/EA/rail/oil integrations and finer geography are
  intentionally deferred until T&E access and review. Seed phrases and account
  panel are test definitions, not validated measures.
- **Next step:** connect the registered adapters to T&E-approved public/API feeds,
  preserve the same contracts and snapshots, review the account panel and topic
  language coverage, then run capped live refreshes before publication.

The release asset uses `uk-atlas-fixture-2026-09-23` and is clearly marked fixture.
