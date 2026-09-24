# Build status

- **Current milestone:** 6 — source-layer expansion and frontend alignment
- **Last completed:** rebuilt the frontend around the approved screen mockup while
  retaining the real UK administrative boundary layer and connected release data;
  the attention timeline now supports line and selectable layered-band plot modes
- **Verification commands:**
  - `.venv/bin/uk-atlas validate-config`
  - `.venv/bin/uk-atlas audit-panels`
  - `.venv/bin/uk-atlas collect-fixture --output data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas collect-layers-fixture --output data/fixtures/data-layers.json`
  - `.venv/bin/uk-atlas check-quality --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas check-layers --input data/fixtures/data-layers.json`
  - `.venv/bin/uk-atlas validate-release --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas export-frontend --input data/fixtures/vertical-slice.json`
  - `.venv/bin/uk-atlas release-verify`
  - `cd frontend && npm test && npm run build`
- **Latest verification:** source-layer fixture contains 335 observations across 11
  registered sources; frontend test and production build pass. The full Python
  suite currently has one pre-existing fixture-audit failure: 15 Bluesky rows in
  the working-tree vertical slice do not reconcile their stored numerator to the
  observed denominator. I left that unrelated data/configuration change untouched.
  `audit-panels` reports expected draft-language, Welsh-coverage and seed-panel
  warnings; `validate-release` remains the release gate.
- **Frontend note:** the latest layout follows the supplied timeline/map mockup
  structure and route map. The visualisation picker now sits at the top of the
  timeline; line mode shows only its axis series builder, while layered mode
  shows only the family/topic layer picker. The timeline plot switch persists as
  `plot=lines` or `plot=layers`; layered controls persist `layers=news,social`
  selections and topic choices, and each rendered band can be hovered or selected.
  Political and search families are visible as pending until their approved feeds
  are connected. Search, local-authority attention, custom metrics and some
  builder controls remain labelled as planned until those datasets and
  interactions are available. The map workspace now uses more of the desktop
  viewport while retaining stacked controls and smaller canvas limits on narrow
  screens.
- **Known issues:** GDELT BigQuery, official Google Trends, production Bluesky
  Jetstream, DESNZ/ONS/HadUK-Grid/EA/rail/oil integrations and finer geography are
  intentionally deferred until T&E access and review. Seed phrases and account
  panel are test definitions, not validated measures.
- **Next step:** connect the registered adapters to T&E-approved public/API feeds,
  preserve the same contracts and snapshots, review the account panel and topic
  language coverage, then run capped live refreshes before publication.

The release asset is a deterministic synthetic fixture identified by its date range
(`uk-atlas-fixture-2026-08-01-2026-08-30`) and is clearly marked `fixture`; it must
not be treated as a research release.
