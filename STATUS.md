# Build status

- **Current milestone:** 4 — frontend pilot and release verification
- **Last completed:** deterministic vertical slice, contract validation, frontend export
- **Verification commands:**
  - `.venv/bin/uk-atlas validate-config`
  - `.venv/bin/uk-atlas collect-fixture --output data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas check-quality --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas export-frontend --input data/fixtures/vertical-slice.json`
  - `cd frontend && npm test && npm run build`
- **Known issues:** GDELT BigQuery, official Google Trends, production Bluesky
  Jetstream, DESNZ/ONS/HadUK-Grid/EA/rail/oil integrations and finer geography are
  intentionally deferred until T&E access and review. Seed phrases and account
  panel are test definitions, not validated measures.
- **Next step:** obtain T&E access approvals, review the account panel and topic
  language coverage, then run a capped real GDELT collection and compare it with the
  fixture before publication.

The release asset uses `uk-atlas-fixture-2026-09-23` and is clearly marked fixture.
