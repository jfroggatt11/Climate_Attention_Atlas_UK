# UK Attention Atlas contracts

The canonical Python definitions live in `src/climate_attention/contracts.py`.
Every serving record carries a release ID, source, observed/collection time,
geography definition, units and quality status. The `DatasetRelease` ties source
snapshots, the combined hash of all release configuration files, Parquet outputs,
Supabase row counts, browser assets and a content hash together. The checked-in
asset is always `status=fixture` until live source captures are approved.

## Attention formulas

- **GDELT news share:** topic-matched distinct URLs on a date divided by the same
  day's distinct captured GDELT UK news URLs. Each denominator carries a deterministic
  capture manifest and universe hash; each topic row carries a matching universe hash
  and matched-index range. The denominator is not all UK news.
- **Bluesky panel share:** topic-matching posts divided by all posts from the
  monitored account panel observed for the same date. The release records the post
  IDs included in that denominator and validates the arithmetic. This is labelled as
  monitored-account posting, not UK social attention.
- **Google Trends:** a 0–100 search-interest index only after official API access;
  it is never merged into news or social counts.
- **MODIS NDVI anomaly:** monthly surface greenness anomaly against a 2001–2020
  baseline, with valid-area coverage. It is not literal grass greenness.

`missing`, `outage`, `unsupported` and `partial` are first-class quality states.
They must remain visible in exports and must not be imputed to zero.

## Configuration status

`config/topics.uk-pilot.yaml` contains four enabled seed topics. The phrase lists
are draft test definitions. Native-speaker review, Welsh and other UK language
coverage, precision/recall validation and classifier review are required before a
research publication can call them validated.
