# Live data on-ramp

The repository is ready for a bounded live pilot, but it is not safe to turn on
continuous refresh yet. The first live release should prove the complete path for
one source and one short period:

```text
provider request -> raw response archive -> resumable run state -> normalized rows
-> release validation -> immutable frontend asset -> optional Supabase publish
```

The checked-in synthetic fixture remains the fallback until a live release passes
the same validation gates.

## Recommended order

### 1. GDELT Web NGrams (first live source)

The existing `GDELTNGramsProvider` already has parameterized SQL, non-billable dry
runs, per-window byte caps, response sinks, request logs and resumable windows. The
remaining work is the live orchestration bridge:

1. Add a `collect-gdelt-live` command that loads the topic, political and geography
   configuration, creates a bounded `CollectionRequest`, and writes raw responses,
   run state and a manifest under `data/`.
2. Add a normalizer from `DailyTrend` to the release contract, retaining the exact
   GDELT denominator scope and source job metadata.
3. Extend the denominator query to emit a reproducible URL-universe digest (the
   current query emits the denominator count; it does not retain the universe
   digest needed by the release contract).
4. Run a seven-day UK-only pilot with all four seed topics, a dry-run byte cap, and
   a small article validation sample. Do not publish it until T&E reviews phrase
   matches and outlet attribution.

### 2. Bluesky monitored panel

The normalizer and observed-post denominator helper already exist. Start with a
bounded AppView collection for the reviewed panel, then add Jetstream/cursor
refresh once the panel and retention rules are approved. The first release should
be labelled as monitored-account posting, never UK-wide social attention.

### 3. MODIS monthly refresh

The satellite module already contains Earthdata/AppEEARS and MOD13C2 helpers. Add a
monthly scheduled job that discovers revised granules, records the product/version,
valid-area fraction and baseline, then writes a source snapshot. This can run after
the GDELT path is proven because it has a different cadence and optional native
dependencies.

### 4. Data categories and publication

Add approved DESNZ/ONS/HadUK-Grid/EA/FIRMS/GDACS sources one at a time. Only after a
live release validates locally should we connect Supabase writes and Netlify
publication. A failed release must remain archived and must not replace the last
verified frontend asset.

## Inputs T&E needs to provide

### Required for the first GDELT run

- A T&E-owned Google Cloud project ID with BigQuery API enabled and billing
  enabled. The project is used to pay for queries; the public GDELT tables remain
  the source dataset.
- A local or CI authentication method. The preferred local path is Google
  Application Default Credentials (`gcloud auth application-default login`); do not
  commit a service-account JSON file.
- A maximum bytes billed for the pilot. The initial recommendation is a seven-day
  cap agreed after the dry-run estimate, with the cap passed to every query.

### Decisions needed before publishing any live release

- Confirm the first date window and whether all four seed topics are in scope.
- Have a native speaker review the current phrases and decide whether Welsh is in
  scope for the first run.
- Review the outlet registry and approve the article URL/sample retention policy.
- Approve the release label and whether the first live output is internal-only.

### Optional after the first GDELT release

- Reviewed Bluesky account panel, stable DIDs, deletion/update handling and
  retention period. Public AppView reads do not require a secret for the initial
  bounded run.
- NASA Earthdata credentials/token for MODIS refreshes.
- NASA FIRMS API key for durable hotspot refreshes.
- Supabase database URL for server-side writes, plus the browser URL/publishable key
  if the live asset will read from Supabase.
- Netlify site/deploy credentials only when an automated publication job is ready.

## Credential handling

Use the untracked `.env` file or the chosen CI secret store. Never paste secrets in
chat, commit them, or put them in frontend environment variables unless the value is
explicitly public. The repository's `.env.example` is a names-only template.

## First-run acceptance gate

A first live run is ready for T&E review when it has:

- a run ID, configuration snapshot and source request logs;
- a raw response archive and provider job/byte metadata;
- complete UK date coverage or explicit missing/outage rows;
- GDELT numerator/denominator arithmetic and denominator-universe checks;
- reviewed article samples and outlet attribution notes;
- a release content hash and configuration hashes;
- a passing `validate-release` and `release-verify` result; and
- no automatic public publication.

