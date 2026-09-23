# Data-layer build status

The source registry is [`config/source_layers.yaml`](../config/source_layers.yaml).
Each layer has a contract, cadence, geography, units, access requirement and
independence note. The local fixture command exercises every layer without making
provider requests:

```bash
PYTHONPATH=src python -m climate_attention.cli collect-layers-fixture
PYTHONPATH=src python -m climate_attention.cli check-layers
PYTHONPATH=src python -m climate_attention.cli export-layer-parquet
```

## Ready now

- DESNZ road fuel price shape (`pence_per_litre`)
- ONS consumer-price shape (monthly index and year-on-year change)
- HadUK-Grid temperature and precipitation anomalies
- Environment Agency flood-alert counts
- Rail delay and cancellation measures
- Brent oil and FTSE 100 market context
- FIRMS hotspot counts
- MODIS MCD64 burned-area shape

These are contract-compatible fixtures and adapter boundaries. They are not live
production refreshes until source terms, identifiers, geography and revision
rules are reviewed.

## Access-pending layers

- Official Google Trends search interest
- Local-authority disruption register

Both are represented explicitly with `unsupported`/`access_pending` status rather
than fabricated zeros. The same prepared observation schema can receive their live
records once access is approved.

## Source invariants

- Every observation has a source, series, date, geography, unit, quality status,
  collection run and release ID.
- Missing, outage, partial and unsupported rows remain visible.
- Source snapshots record coverage, request count, endpoint, completeness and rate
  limit notes.
- No layer is merged into the attention series without an explicit unit and
  denominator decision.

The Parquet command writes an atomic `data/processed/layer_observations.parquet`
archive. The processed directory is intentionally gitignored; release manifests
carry its path and the active release ID.
