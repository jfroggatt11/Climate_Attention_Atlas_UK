# Source status at initial build

| Source | Pilot state | Scope and next action |
| --- | --- | --- |
| GDELT Web NGrams / BigQuery | Fixture + adapter port | Run capped real UK collection after T&E billing/access approval. |
| GDELT DOC/timeline | Adapter port | Secondary comparison only; do not merge measures. |
| Bluesky AppView | Seed fixture | Approve reviewed account panel, then add Jetstream history/cursor refresh. |
| Google Trends | Deferred | Official API access required; experimental collector remains test-only. |
| MODIS MOD13C2 | Imported fixture | Refresh monthly and retain baseline/valid-area metadata. |
| MODIS MCD64 / FIRMS | Event fixture + adapter port | Keep hotspots separate from named events and burned area. |
| GDACS | Event fixture + adapter port | Named alerts, not a complete UK local incident register. |
| DESNZ, ONS, HadUK-Grid, Environment Agency, rail, oil | Integration points only | Add source contracts and access-owned collectors in later milestones. |
