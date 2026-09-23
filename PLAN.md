# UK Attention Atlas initial build plan

## Milestones and acceptance checks

1. **Foundation and contracts** — copy approved specifications; define versioned
   topic, article, social, search, event, physical, manifest and release contracts;
   validate configuration and document language gaps. Acceptance: `validate-config`
   passes and no secret/generated archive is tracked.
2. **Reliable vertical slice** — run the deterministic capped fixture through GDELT
   news counts and aligned captured-news denominator, Bluesky monitored-panel posts,
   MODIS NDVI anomaly and one GDACS/FIRMS-style event. Acceptance: quality checks
   pass, missing days remain missing, and release manifest is reproducible.
3. **Serving/export layer** — materialise prepared rows, provide Supabase payloads,
   and export one release asset with a release ID. Acceptance: export contract and
   release verification pass.
4. **Frontend pilot** — adapt the supplied mockup into Timeline, UK map scaffolding,
   Saved views, Data and Methods routes, URL state, freshness/status metadata, chart
   evidence and export affordances. Acceptance: production build and frontend tests
   pass.
5. **T&E handover and validation** — local preflight is now implemented with
   configuration/panel audits, cross-table release checks and a pre-registration
   worksheet. Remaining work is T&E-owned: source access, native-speaker review,
   classifier/outlet audits, pre-registered hypotheses and approved geographies.
   Acceptance: decisions below are resolved before a published research release.
6. **Source-layer expansion** — build the prepared observation and source-snapshot
   contracts for prices, weather, physical hazards, disruption, markets and deferred
   search/local feeds. Acceptance: every registered layer has units, cadence,
   provenance, quality status and a deterministic fixture or explicit access-pending
   state.

## Decisions still needed from T&E

- Approve the reviewed Bluesky account panel and retention/deletion policy.
- Approve topic translations and Welsh/other UK language coverage before calling
  phrases validated.
- Provide T&E-owned BigQuery, Supabase and Netlify projects/secrets.
- Confirm article URL retention and republication policy.
- Confirm MODIS refresh cadence and whether a grassland/cropland mask is needed.
- Choose the official Google Trends API access path and publication terms.
- Approve county/local-authority boundary source and unsupported-geography display.
- Pre-register primary hypotheses, multiple-testing decisions and matched-date checks.

## Progress log

- 2026-09-23: Milestones 1–4 completed; the detailed Natural Earth UK boundary layer
  replaced the schematic map shapes.
- 2026-09-23: Milestone 5 local readiness completed: `audit-panels`,
  `validate-release`, cross-table release-ID checks and the validation/pre-registration
  worksheet are available. External validation and access decisions remain open.
- 2026-09-23: Milestone 6 source-layer expansion completed locally: 11 registered
  layers, 335 source-separated fixture observations, source snapshots, CSV/JSON
  parsers, provider request-plan adapters, unit validators, `collect-layers-fixture`
  and `check-layers`. Official Trends and local disruption remain explicit
  `access_pending` records.
- 2026-09-23: Frontend alignment pass replaced the earlier dark/sidebar pilot with
  the approved light atlas shell and mockup structure: timeline control rows,
  two-axis series builder, event chips, measure cards, chart/evidence split,
  three-column UK map workspace, time controls, saved-view URLs, `/data` source
  catalogue and source-aware `/methods` view. The prototype now uses the approved
  route map and labels unavailable geography/feeds explicitly.
- 2026-09-23: Applied viewport-fit tuning to the mockup-aligned frontend: capped
  map height, reduced medium-width column sizes, and responsive map playback controls.
- 2026-09-23: Increased the desktop map workspace width and canvas height after
  screenshot review so the map is the dominant surface again; medium and mobile
  breakpoints retain bounded heights and stacked controls.
