# UK polling and public-attitudes source review

**Review date:** 2026-10-01  
**Use case:** UK Attention Atlas: compare public attitudes with news, search, social, events, physical conditions and economic context.  
**Decision status:** source review; no production polling feed is enabled by this document.

## Short answer

Yes. There is enough public, free material to start a reproducible and refreshable polling layer, but it should not be built from a generic poll scrape.

The recommended backbone is the **DESNZ Public Attitudes Tracker (PAT)**. It is a UK-wide, nationally representative survey of people aged 16+, with repeated climate, net-zero, renewable-energy and energy questions. The latest release supplies a questionnaire, a time-series workbook and cross-tabulations. It has run quarterly/triannually since autumn 2021, so it is suitable for a recurring series, although it is not daily and the public release is an aggregate workbook rather than respondent microdata.

Add **ONS Opinions and Lifestyle Survey climate releases** as a supporting series. These are free official Great Britain estimates with downloadable workbooks and repeated climate questions, but the climate module is irregular and the next release is not guaranteed. Use it for corroboration and event-aligned analysis, not as a regularly spaced panel.

For the EV topic, add the **DfT EV Driver Behaviours and Attitudes Tracker**. It publishes survey datasets, but its population is EV/BEV/PHEV drivers, so it measures owner/driver experience and barriers rather than whole-population opinion.

Use **BSA and BES** for historical context and question-level validation. They are accessible through the UK Data Service, usually with registration and end-user terms, and release timing is too slow/irregular to be the live refresh backbone. Treat public YouGov/Ipsos/BPC tables, Climate Barometer, CAST and commissioned Greenpeace polls as supplementary or event-triggered inputs unless the owner confirms a durable machine-readable feed and redistribution rights.

## Source matrix

| Source | What it gives this project | Public/free access | Refreshability | Main limitation | Recommendation |
|---|---|---|---|---|---|
| [DESNZ Public Attitudes Tracker](https://www.gov.uk/government/collections/public-attitudes-tracking-survey) | Climate-change concern, net zero, renewable energy, energy bills, behaviours and policy attitudes; repeated core questions | GOV.UK workbooks, questionnaires and technical reports; government material is reusable under the OGL subject to attribution | **High for a public-release feed**: triannual from spring 2024, earlier quarterly waves; no respondent API | Aggregate releases only; question wording and modes must be checked across waves | **Production backbone** |
| [ONS OPN: environment and climate change](https://www.ons.gov.uk/economy/environmentalaccounts/datasets/publicattitudestowardstheenvironmentandclimatechangebycharacteristicsgreatbritain) | Importance/salience, concern, experienced and expected climate impacts, demographics | Free XLSX releases; ONS content is generally OGL with attribution | **Medium**: repeated releases, but irregular and next release may be unannounced | Great Britain rather than UK; no guaranteed cadence; estimates can be revised | **Supporting official series** |
| [DfT EV driver behaviours and attitudes tracker](https://www.gov.uk/government/publications/electric-vehicle-ev-driver-behaviours-and-attitudes-tracker) | EV adoption barriers, charging, confidence, satisfaction and driver experience | Free GOV.UK ZIP/XLSX survey datasets and reports | **Medium/low**: annual tracker releases; current page has years 1 and 2 | EV/PHEV drivers only; not general UK climate or transport opinion | **EV context layer** |
| [British Social Attitudes](https://natcen.ac.uk/participant-contents/british-social-attitudes) / [UKDS study 9363](https://doc.ukdataservice.ac.uk/doc/9363/mrdoc/UKDA/UKDA_Study_9363_Information.htm) | Long-running repeated attitudes; climate belief and environmental action items in selected waves | Research access through UK Data Service; registration/EULA and commercial-use approval may apply | **Medium for backfill, low for monitoring**: annual survey, release lag | Mode and wording changes; climate items are not in every wave; not an open unauthenticated API | **Historical validation/backfill** |
| [British Election Study panel](https://datacatalogue.ukdataservice.ac.uk/variables/variable/a3893c91-df87-4a4d-bab3-40a485d51fea) | Longitudinal political attitudes and subgroup analysis; environmental items where asked | UKDS registered access | **Low for live refresh**; panel data are released in editions | Election/politics focus; question availability varies; use terms apply | **Historical/subgroup analysis** |
| [Climate Barometer](https://climatebarometer.org/the-tracker/) | Twice-yearly matched public and MP climate opinion; core repeated questions | Public visualisations/questionnaires; underlying data can be requested | **Medium if a relationship is maintained; low for unattended ingestion** | Provider changed from YouGov to Savanta in 2026; no stable public data endpoint; provider/house effects | **Partner-supplied supplement** |
| [YouGov survey results](https://yougov.com/survey-results) and BPC member tables | Fast topical climate, energy and EV questions with question wording and toplines | Many public PDFs/XLSX files; BPC members commit to publishing methodological details | **Low as a general feed**: publication pages and files vary; no public polling API | Sponsor, wording, sample, mode and rights vary; no stable series for every topic | **Manual/event supplement** |
| [Ipsos UK climate work](https://www.ipsos.com/en-uk/topic/climate-change) | High-quality topical and international climate polls | Public reports/toplines | **Low as a general feed**; raw data/API not generally public | Commissioned question sets and publication rights vary | **Manual/event supplement** |
| [CAST public views on climate portal](https://cast.ac.uk/cast-tools/cast-data-portal-public-views-on-climate/) | Research series on climate perceptions, action, trust and responsibility | Public dashboard and briefings | **Low**: published research portal, not an active release feed | Historic study series; not a continuously maintained UK tracker | **Context/reference only** |
| Greenpeace-commissioned polls | Campaign-specific questions and topical snapshots | Usually public report/topline | **Low**: bespoke commissioning and rights | Sponsor framing and non-comparable question designs; no assured repeat cadence | **Do not use as the default backbone** |

### Why DESNZ is the best starting point

The Spring 2026 PAT page identifies it as a nationally representative UK survey of adults aged 16+ and provides a questionnaire, time-series workbook and cross-tabulation workbook. The tracker began in autumn 2021; from spring 2024 it moved to spring, summer and winter waves. That combination gives a stable unit of analysis, a documented questionnaire and enough repeated questions to study change without inventing daily values.

### Why the other sources should remain separate

A poll estimate is a response share from a defined population and question. It is not an article count, a social-post count or a search index. The sources differ in geography (UK vs Great Britain), population (all adults vs EV drivers vs MPs), mode, weighting, sponsor and wording. Combining them into one line or filling gaps by interpolation would create a measure that no poll actually observed.

## Proposed measurement contract

Use a dedicated PollObservation contract (or extend ObservationRecord without losing the fields below). One row should be one response option for one question in one wave.

Required fields:

- source, series_id, wave_id, release_id, source_url
- fieldwork_start, fieldwork_end, release_date
- geography and population (for example, UK, GB, adults_16_plus, EV_drivers)
- question_id, exact question_text, response_code, exact response_label
- estimate, unit=percent, unweighted_n (and weighted base when supplied)
- mode, sampling_design, weighting_summary
- questionnaire_version, sponsor, pollster_or_producer
- source_file_url, source_file_sha256, retrieved_at, licence
- quality_status, revision_status, and a structured comparability_flags object

Keep question metadata in a separate crosswalk keyed by source + series_id + question_id. A series is comparable only when geography, population, wording, response scale, mode and weighting are compatible. Store don't know, refusals and not-applicable categories rather than silently dropping them.

For the Atlas display, use irregular points or a step/segment view with the fieldwork window in the tooltip. Do not interpolate a poll to daily values and do not use it as a denominator for GDELT, Bluesky or search.

## Refresh and reproducibility design

1. **Discover releases.** Keep a small source manifest with the official landing page, expected attachment labels, cadence and parser version. For GOV.UK, use the unauthenticated [Content API](https://content-api.publishing.service.gov.uk/) to retrieve structured page metadata and attachment links instead of scraping rendered HTML.
2. **Capture immutably.** On each scheduled run, download the landing-page JSON, questionnaire, time-series workbook, crosstabs and technical report where available. Save each raw file under data/raw/polling/<source>/<release_id>/ and record retrieval time, URL, HTTP metadata and SHA-256.
3. **Parse deterministically.** Pin the parser and workbook sheet/column mapping. Convert percentages and bases to a tidy Parquet table. Preserve the original workbook and a parser log; fail when an expected sheet, question ID or response label disappears.
4. **Crosswalk before comparison.** Require an explicit mapping from a new wave to an existing series_id. A new wording, response scale, population, mode or weighting scheme creates a new series or a flagged break.
5. **Validate and stage.** Check duplicate (source, wave, question, response) keys, percentages in range, response shares summing to approximately 100% where appropriate, valid fieldwork dates, population/geography, and source-file hashes. Stage a candidate release; do not overwrite the published release.
6. **Publish with provenance.** Publish only after the source snapshot is complete. Keep old releases immutable and mark later corrections as superseding releases. Expose the source link, fieldwork dates, exact wording and freshness in the UI.
7. **Schedule realistically.** Run discovery weekly (cheap), poll the DESNZ collection page for a new wave, and run the full parser when a new asset hash appears. Expect three PAT releases per year. Run an ONS check monthly/quarterly but accept that it may yield no new climate module. Ingest BSA/BES/YouGov/Ipsos/Climate Barometer only when a reviewed release is found.

## Suggested first implementation

- Add desnz_pat and ons_opn_climate as separate registered layers; leave the current polling_opinion placeholder out of production.
- Build one DESNZ collector first. Start with the time-series workbook plus questionnaire and technical overview; add crosstabs after the core parser is validated. Run `.venv/bin/uk-atlas collect-desnz-pat-live` to discover the newest GOV.UK release, archive the landing-page JSON and workbook under `data/live/desnz_pat/raw/`, and write `data/live/desnz_pat/bundle.json`.
- Keep the poll metadata on the normalized observation rows and implement the question crosswalk before adding any third-party poll.
- Backfill PAT waves from autumn 2021 onward where the time-series workbook exposes them.
- Add ONS 2021, 2022, 2023, 2024 and 2025 climate releases as separate irregular observations, preserving the GB geography label.
- Add DfT EV tracker as a separate ev_attitudes layer, not as a climate-concern series.
- Keep the UI label explicit: “Public attitudes (DESNZ PAT; triannual, UK adults 16+)” and “Public attitudes (ONS OPN; irregular, Great Britain)”.

## What “free” means here

The government and ONS aggregate releases are free to download and generally reusable with attribution. UKDS datasets are free for research access but require registration and terms; they should not be treated as unrestricted public files. Public YouGov/Ipsos/BPC tables are free to view/download, but a public file is not automatically a licence to bulk-republish its contents or to scrape a site continuously. Store source links and hashes, publish derived estimates with attribution, and request permission where a source’s redistribution terms are unclear.

## Acceptance criteria for production

A polling source is ready for the Atlas only when:

- the exact question and response options are archived;
- fieldwork dates, population, geography, mode, sample and weighting are present;
- the source file and landing-page snapshot are hashable and reproducible;
- the parser can detect a changed workbook layout or question wording;
- missing waves remain missing rather than interpolated;
- the licence/attribution decision is recorded;
- a second run over the same source files produces the same tidy output.
