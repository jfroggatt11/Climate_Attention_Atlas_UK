# UK Attention Atlas — project audit and recommendations

Saved: 24 September 2026

This records the read-only audit delivered in the conversation. It describes the
repository at the time of that review; saving this report does not constitute a
new verification run. No code or existing documentation was changed during the
audit.

## Scope and overall assessment

The audit covered `PLAN.md`, `STATUS.md`, the README, methodology and operations
documents, contracts, configuration, fixtures, frontend, tests, and the Supabase
migration.

The current state is a **fixture-level engineering prototype**, not yet a
methodologically publishable research release.

Independently verified during the audit:

- Frontend tests: 1 test passed.
- Frontend production build: passed, with a large-bundle warning.
- Python checks were not rerun because the environment lacked PyYAML, Pydantic,
  PyArrow, and pytest; package installation could not reach the package index.
- The working tree had no tracked changes.

The strongest parts are the separation of news, social, search, physical, and
economic measures; explicit units and denominator definitions; visible missingness
states; source snapshots; independent event concepts; and the clear warning that
the pilot makes no causal claim.

## P0 — Must resolve before treating results as evidence

- The current release is synthetic. The fixture generates formulaic news, social,
  price, weather, rail, fire, and NDVI values in
  [pipeline.py](../src/climate_attention/pipeline.py) and
  [source_layers.py](../src/climate_attention/source_layers.py). The README and plan
  describe “refreshed” MODIS data, but the release contains a single synthetic NDVI
  record.
- The Bluesky denominator is fabricated: `panel_total` is set to
  `18 + index % 5`, while only three seed accounts generate a few posts. It is not
  the number of observed posts from the monitored panel
  ([pipeline.py](../src/climate_attention/pipeline.py)).
- The GDELT numerator and denominator are only contract-shaped. The validator
  checks that the denominator value is copied consistently, but does not verify
  that the share equals numerator ÷ denominator or that the denominator came from
  the same captured URL universe
  ([validation.py](../src/climate_attention/validation.py)).
- The fixture is not byte-for-byte reproducible because
  `DatasetRelease.created_at` uses the current time
  ([pipeline.py](../src/climate_attention/pipeline.py)).
- The release hash covers only the topic configuration, not the account panel,
  outlet registry, source-layer registry, geography configuration, or political
  configuration.
- `release-verify` checks that a few fields exist; it does not verify hashes,
  output files, row counts, release status, or frontend asset contents
  ([cli.py](../src/climate_attention/cli.py)).

## P1 — Must resolve before a live pilot

- `docs/methodology.md` is from the earlier MVP and conflicts with the current UK
  pilot. It says country denominators are optional and describes two prototype
  topics, while the current contracts and frontend treat the captured-news
  denominator as central and use four topics.
- Several documents reference files that do not exist, including
  `IMPROVEMENTS_PHASE1.md`, `config/topics.multilingual.example.yaml`, old migration
  files, and old analysis modules.
- `docs/operations.md` is largely an old MVP operations guide. It documents
  commands that are absent from this repository, including `collect-trends`,
  `estimate-ngrams`, `collect-ngrams`, `compare-sources`,
  `collect-modis-vegetation`, and `sync-analysis-supabase`.
- The current CLI does not perform several actions its documentation claims:
  `aggregate` only writes a quality report; `sync-supabase` writes a JSON payload
  and `--apply-migration` does not connect to Supabase; `runs inspect|retry` is a
  placeholder; and `collect` exits with a gated status.
- The frontend currently loads only static
  `frontend/public/data/release.json`; it does not use Supabase. The architecture
  briefing says Supabase is required for the current experience, which is no
  longer true.
- The Supabase migration creates tables but does not define the RLS, grants, or
  read/write policies described elsewhere.
- The source registry omits `modis_mod13c2`, even though the vertical slice and
  frontend use MODIS NDVI.
- The registry says Environment Agency coverage is `GB`, although the planned
  source is England-only. Geography needs to be explicit by nation and source.
- Weekly DESNZ and monthly HadUK-Grid layers are emitted as daily fixture
  observations. This is acceptable for a smoke fixture only if clearly labelled;
  it is not a valid temporal representation.
- The map uses a Natural Earth administrative dataset with historical boundaries,
  not the ONS geography promised in the plan. It must remain labelled as display
  scaffolding until current, versioned UK geography is adopted.
- The local disruption snapshot is reported as `fixture` because it contains
  placeholder partial rows, despite the layer being `access_pending`. The
  frontend also counts placeholder values as observed.
- The map displays the monthly NDVI value for any selected day in the release
  instead of respecting monthly temporal resolution.
- Only one frontend test exists. There are no meaningful tests for data loading,
  denominator display, missingness, export, map behaviour, route handling, or
  release integrity.

## P2 — Important methodological and operational improvements

- Complete native-speaker review, Welsh coverage decisions, phrase
  precision/recall sampling, outlet-country audits, and political-signal
  validation.
- Approve the Bluesky panel, stable DIDs, deletion/update handling, account
  categories, retention rules, and whether the panel is suitable for any
  descriptive comparison.
- Define source-specific revision, timezone, cadence, licensing, release/version,
  and historical-coverage fields.
- Add boundary version and geography-source metadata to every spatial
  observation.
- Keep article publishing geography, article-mentioned geography, event location,
  and audience geography as separate fields.
- Pre-register primary outcomes, exposure definitions, date windows, lag rules,
  minimum completeness, missing-data handling, multiple-testing decisions, and
  sensitivity analyses.
- Add checks for expected cadence, numerator/denominator arithmetic, denominator
  uniqueness, source snapshot alignment, row-count reconciliation, unsupported
  geography, and partial coverage.
- Add a real release process with immutable snapshot IDs, hashes for every
  output, one active release ID, atomic publication, rollback, and backup/restore
  procedures.
- Add a Python lockfile or reproducible CI environment so the documented
  verification commands can actually be rerun.
- Review data rights for article URLs, social posts, market data, and provider
  redistribution before publication.

## Recommended forward plan

1. **Documentation reset:** make `PLAN.md`, `STATUS.md`, `docs/methodology.md`,
   `docs/operations_pilot.md`, and `docs/data-dictionary.md` the current canonical
   documents. Mark the old MVP operations and architecture documents as
   historical.
2. **Release integrity:** make fixture generation deterministic, hash every
   configuration and output, and strengthen `validate-release` and
   `release-verify`.
3. **Measurement validation:** replace fabricated fixture denominators with
   internally coherent synthetic records, then run capped real GDELT and Bluesky
   collections.
4. **Source and geography approval:** register MODIS NDVI, correct nation
   coverage, choose ONS geography, and implement only sources with confirmed
   terms and revision rules.
5. **Pre-registration and review:** complete topic, outlet, account, denominator,
   language, and hypothesis review before interpreting associations.
6. **Live pilot:** run a bounded UK period with GDELT, reviewed Bluesky, MODIS,
   one approved economic series, and one approved disruption source. Publish a
   coverage report alongside the data.
7. **Research release:** only then enable public-facing release status, case
   studies, exports, and any inferential or comparative analysis.

The current work is a useful foundation, but the release should be labelled
**synthetic fixture / engineering demonstration** until the denominator,
provenance, source-access, validation, and release-control issues above are
resolved.
