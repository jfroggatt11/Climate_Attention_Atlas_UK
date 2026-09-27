# UK Attention Atlas initial build plan

## Milestones and acceptance checks

1. **Foundation and contracts** — copy approved specifications; define versioned
   topic, article, social, search, event, physical, manifest and release contracts;
   validate configuration and document language gaps. Acceptance: `validate-config`
   passes and no secret/generated archive is tracked.
2. **Reliable vertical slice** — run the deterministic capped synthetic fixture through GDELT
   news counts and aligned captured-news denominator, Bluesky monitored-panel posts,
   MODIS NDVI anomaly and one GDACS/FIRMS-style event. Acceptance: quality checks
   pass, missing days remain missing, denominators reconcile to captured/observed
   universes, and the release manifest is byte-for-byte reproducible.
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
- 2026-09-24: Added the main timeline plot switch: the existing multi-series line
  chart can now be changed to a layered relative-intensity band view. The mode is
  URL-persisted, uses the selected topics, marks event periods, and states that
  each layer is scaled to its own peak.
- 2026-09-24: Revised the layered view after review: it now has selectable News and
  Social families, topic chips, band hover/click highlighting, compact geometry,
  and explicit pending states for Political and Search until approved feeds exist.
- 2026-09-24: Cleaned the timeline hierarchy after review: visualisation selection
  moved to the top of the page, and the line axis builder and layered family/topic
  picker are now mutually exclusive.
- 2026-09-24: P0 release-integrity pass completed: fixture timestamps and content
  hashes are deterministic, all release configuration inputs are hashed, GDELT and
  Bluesky denominators reconcile to explicit universes, release verification checks
  files/assets/row counts, and the map respects monthly NDVI periods.
- 2026-09-25: Added the planned polling opinion layer (BES, YouGov, Ipsos and
  Greenpeace candidates) as an access-pending source with poll metadata and
  publication-rights requirements. The frontend now uses a shared ordered layer
  taxonomy and colour system across timeline, map, data and methods views; pending
  layers remain visible and are labelled rather than plotted as observed values.
- 2026-09-25: Reworked the timeline picker to follow category → data source →
  measure. Available measures are organised in collapsible data categories and can now be
  assigned to either chart axis with unit-compatible axes, source labels and
  URL-persisted series selections. Events remain separate x-axis markers.
- 2026-09-27: Published the three-level layer hierarchy: External events and conditions, Attention and public attitudes, and Secondary impacts and responses. Energy markets are kept with external conditions for Brent shocks; household prices, shares, policy and disruption remain secondary impacts.

## Shared data-layer taxonomy

The atlas uses three top-level groups across every page and visualisation: **External events and conditions** (dated hazards and geopolitical events, plus environmental measures, energy-market shocks and other external conditions), **Attention and public attitudes** (News, Search, Social and Polling), and **Secondary impacts and responses** (Economic, Political and Disruption). Each category has one label and colour in the picker, axes, map controls, methods page and source registry. A source's group describes its analytical role, not a causal claim: temperature, rainfall, greenness and burned area are observations, while events are dated markers.

Events are stored separately from time-series measures: single dates render as points and start/end ranges as shaded regions on the X axis. External conditions and secondary impacts can be added to either Y axis when an observed measure is available. Pending categories and sources remain visible with their access status.