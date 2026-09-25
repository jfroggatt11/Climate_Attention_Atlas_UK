# Source status at initial build

| Source | Pilot state | Scope and next action |
| --- | --- | --- |
| GDELT Web NGrams / BigQuery | Fixture + adapter port | Run capped real UK collection after T&E billing/access approval. |
| GDELT DOC/timeline | Adapter port | Secondary comparison only; do not merge measures. |
| Bluesky AppView | Seed fixture | Approve reviewed account panel, then add Jetstream history/cursor refresh. |
| Google Trends | Deferred | Official API access required; experimental collector remains test-only. |
| MODIS MOD13C2 | Live adapter + candidate | Refresh monthly and retain baseline/valid-area metadata. |
| MODIS MCD64 / FIRMS | Event fixture + adapter port | Keep hotspots separate from named events and burned area. |
| GDACS | Event fixture + adapter port | Named alerts, not a complete UK local incident register. |
| DESNZ, ONS, HadUK-Grid, Environment Agency, Brent | Live adapters / snapshots | Refresh official public feeds; preserve revisions and current-only flood semantics. |
| Tesla, BP, Shell | Exploratory market adapter | Refresh daily closes, then confirm redistribution terms before publication. |
| MODIS MCD64 burned area | Live AppEEARS adapter | Use Earthdata credentials for bounded Burn_Date tasks; retain native rasters and task IDs. |
