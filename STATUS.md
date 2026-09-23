# Build status

- **Current milestone:** 5 — T&E handover and validation readiness
- **Last completed:** detailed Natural Earth UK map layer, configuration/panel audit,
  cross-table release audit and pre-registration worksheet
- **Verification commands:**
  - `.venv/bin/uk-atlas validate-config`
  - `.venv/bin/uk-atlas audit-panels`
  - `.venv/bin/uk-atlas collect-fixture --output data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas check-quality --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas validate-release --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas export-frontend --input data/fixtures/vertical-slice.json`
  - `cd frontend && npm test && npm run build`
- **Latest verification:** 37 Python tests passed; frontend test and production
  build passed; `audit-panels` reports expected draft-language, Welsh-coverage and
  seed-panel warnings; `validate-release` passes.
- **Known issues:** GDELT BigQuery, official Google Trends, production Bluesky
  Jetstream, DESNZ/ONS/HadUK-Grid/EA/rail/oil integrations and finer geography are
  intentionally deferred until T&E access and review. Seed phrases and account
  panel are test definitions, not validated measures.
- **Next step:** obtain T&E access approvals, review the account panel and topic
  language coverage, complete the worksheet in `docs/VALIDATION_AND_PREREGISTRATION.md`,
  then run a capped real GDELT collection and compare it with the fixture before
  publication.

The release asset uses `uk-atlas-fixture-2026-09-23` and is clearly marked fixture.
