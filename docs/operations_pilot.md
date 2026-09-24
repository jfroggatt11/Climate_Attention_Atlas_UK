# Pilot operations

The live-data sequence and credential checklist are maintained in
[LIVE_DATA_ONRAMP.md](LIVE_DATA_ONRAMP.md). Start there before enabling a provider.

The commands below are intentionally separate so collection, analysis,
synchronisation and publication remain observable operations.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/uk-atlas validate-config
.venv/bin/uk-atlas audit-panels
.venv/bin/uk-atlas dry-run --start 2026-08-01 --end 2026-08-30
.venv/bin/uk-atlas collect-fixture
.venv/bin/uk-atlas collect-layers-fixture
.venv/bin/uk-atlas check-quality
.venv/bin/uk-atlas check-layers
.venv/bin/uk-atlas export-layer-parquet
.venv/bin/uk-atlas validate-release
.venv/bin/uk-atlas aggregate
.venv/bin/uk-atlas sync-supabase       # payload only unless --apply-migration is explicit
.venv/bin/uk-atlas export-frontend
.venv/bin/uk-atlas release-verify
cd frontend && npm install && npm run test && npm run build
```

For a real run, the T&E-owned BigQuery project and billing cap must be supplied to
the existing `gdelt_ngrams` adapter. The provider's request logs, resumable run
state and manifest are retained under the research archive path selected by T&E.
The experimental Google Trends adapter can plan requests, but official API access
is required before publishing search interest. Public Bluesky AppView reads are
rate-limited and the monitored panel must be approved before a durable Jetstream
refresh.

The release ID is checked by `release-verify`. Rollback means republishing the
previous verified `frontend/public/data/release.json` and retaining the failed run
manifest; it does not delete source archives.
