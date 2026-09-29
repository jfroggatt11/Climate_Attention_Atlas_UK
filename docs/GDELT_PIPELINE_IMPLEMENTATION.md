# GDELT article-level pipeline implementation

The first implementation slice of `GDELT_PIPELINE_PLAN.md` is now in the
repository. It is deliberately offline and billable-query free until a reviewed
outlet universe, BigQuery project and byte cap are supplied.

## Implemented

- Topic-independent article identities with conservative URL normalization and
  URL alias retention.
- GAL inventory and GKG enrichment SQL builders. GKG is aggregated per URL/day
  and left-joined so missing GKG records do not remove GAL inventory rows.
- Explicit contracts for capture membership/manifests, source snapshots,
  tag definitions/assertions/resolutions, evidence, entities, events, places,
  location roles, coverage and daily metrics.
- Conflict-aware tag resolution. A positive and negative assertion resolves to
  `unknown`; absent assertions are not created for unevaluated articles.
- Event-link candidates that remain ambiguous until contextual review, including
  unnamed hazard candidates and a distinct event category path.
- Null-safe coverage and conditional metric arithmetic with reconciled unknown
  counts and zero-denominator handling.
- A Supabase migration for the article, evidence, tagging, coverage and daily
  metric tables (`supabase/migrations/002_gdelt_article_pipeline.sql`).
- A resumable `collect-gdelt-articles` orchestration path with atomic stage
  checkpoints, raw query archives, per-query and cumulative byte caps, and
  candidate release output.
- Versioned event registry loading, event-link candidate output, analytical
  Parquet snapshots, and a validated read-only serving payload.
- Dry-run, release validation, run inspection, and reproducible human-review
  sampling and precision/recall scoring CLI commands.
- Distinct `fuel_prices` taxonomy tag, dated political identity seeds and outlet
  metadata fields for edition, aliases, publishing geography and coverage areas.

## Local checks

```bash
.venv/bin/pytest -q
.venv/bin/python -m climate_attention.cli gdelt-sql --mode joined
.venv/bin/python -m climate_attention.cli dry-run --start 2026-08-01 --end 2026-08-07
.venv/bin/python -m climate_attention.cli estimate-gdelt-articles \
  --start 2026-08-01 --end 2026-08-07 \
  --billing-project "$GCP_PROJECT" --max-bytes 100000000000
```

`gdelt-sql` only prints parameterized SQL. It does not contact BigQuery. A live
collector requires the inputs listed in `LIVE_DATA_ONRAMP.md`. Collection writes
a candidate bundle under `data/processed/` and never publishes it automatically.
