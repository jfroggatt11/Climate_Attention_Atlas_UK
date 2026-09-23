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
5. **T&E handover and validation** — obtain source access, native-speaker review,
   classifier/outlet audits, pre-register hypotheses and add approved geographies.
   Acceptance: decisions below are resolved before a published research release.

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
