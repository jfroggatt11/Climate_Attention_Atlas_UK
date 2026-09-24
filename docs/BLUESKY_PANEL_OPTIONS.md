# Bluesky panel options

## What the current collector can and cannot identify

The current adapter collects posts from a configured list of stable Bluesky DIDs.
It records the DID, handle, post URI, timestamp, text, topic labels, cursor and
delete/update flags. It does not observe a validated author-country field, and the
`country: GB` value in `config/account_panel.yaml` is a project assertion that
still needs review.

English text is not a location signal. A post mentioning the UK may be written by
someone elsewhere, and a UK author may write about another country. A UK handle,
organisation name or topic keyword can support panel inclusion or content
classification, but none proves the author's residence or the audience's location.

## Bluesky's built-in trends endpoints

Bluesky does expose compiled current trends. The official `app.bsky.unspecced.getTrends`
lexicon describes them as trends “on the network” and exposes a `limit` parameter,
not a country or region parameter. The related `getTrendingTopics` endpoint accepts
an optional viewer DID and a limit, also without a country selector. Trend records
include a post count and actors, but no country dimension.

The official client sends user-interest topics and an `Accept-Language` preference
when requesting trends. Those inputs can personalize discovery and language, but
they are not a reproducible UK geography filter. We could archive this endpoint as
a separate **global Bluesky trends snapshot**, or use it to discover candidate UK
accounts and topics. It cannot replace a UK-associated panel or provide a UK social
denominator.

## Measurement choices

### A. UK-associated monitored panel — recommended first measure

Create a reviewed, stratified list of stable DIDs with documented inclusion
evidence. Possible strata are UK civil-society organisations, UK journalists,
politicians, researchers, transport/climate specialists, and regional voices.
Measure:

```text
topic posts from the reviewed panel on a day
---------------------------------------------
all observed posts from that panel on the day
```

This is a descriptive measure of posting by the monitored panel. It can support
within-panel trends and transparent comparisons when panel composition stays fixed.
It cannot be labelled UK social attention or treated as a population estimate.

### B. UK-referenced social content

Collect a broader feed and classify posts that mention UK places, institutions,
policies or other pre-registered UK references. This estimates attention to UK
references in the collected feed, not posting by people in the UK. It has keyword
coverage and false-positive/false-negative risks and needs its own denominator.

### C. Representative UK social attention

Do not promise this in the pilot. It would require a defensible population sampling
frame, platform coverage, geography metadata or validated location inference, and
stable access to the relevant stream. The current repository cannot support that
claim.

## Decisions for T&E

1. Which estimand should the first chart use: **A**, **B**, or both as separate
   labelled series?
2. For A, which strata and target counts should the panel contain? Avoid a panel
   made only of T&E and close allies if comparisons are intended.
3. What qualifies an account for inclusion: UK base, UK remit, self-declared public
   location, organisation registration, UK reporting beat, or another rule?
4. Should Welsh-language and other UK-language accounts be included in the first
   panel, and how should language-specific topic phrases be reviewed?
5. What retention and deletion policy applies to post text, URLs, DIDs and profile
   snapshots?
6. Is the result internal monitoring only, or may it appear in a public release?

## Data-quality rules once A is approved

- Freeze the DID list and panel version before each release; retain the review date
  and inclusion evidence.
- Collect all posts from included accounts for each covered day, including posts
  that match no topic, so the denominator is observable.
- Preserve deletions, updates, cursors and incomplete-day status; never convert an
  unavailable account or feed interval to zero posts.
- Keep account category and panel membership separate from any inferred geography.
- Report panel composition and observed coverage beside every social series.
- Treat topic matching, author geography and audience geography as separate fields.
