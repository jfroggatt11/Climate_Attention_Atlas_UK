"""Article-level building blocks for the versioned GDELT tagging pipeline.

The module is intentionally provider-light.  It normalizes GAL observations,
keeps many-to-many evidence without multiplying article counts, and exposes
bounded SQL builders for Web NGrams and GKG.  Network execution belongs to the
existing BigQuery adapter; these functions are safe to exercise in fixtures.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any, Iterable, Mapping, Sequence

from .contracts import (
    Article,
    ArticleEventLink,
    ArticleTag,
    ArticleTagAssertion,
    CaptureMembership,
    ClassificationCoverage,
    DailyMetric,
    EvaluationStatus,
    TagEvidence,
)

_TABLE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "mc_cid", "mc_eid"}


def normalize_url(url: str) -> str:
    """Conservatively canonicalize a URL while retaining content query keys."""
    value = url.strip()
    if not value:
        raise ValueError("article URL must not be empty")
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    if not parsed.netloc:
        raise ValueError(f"article URL has no host: {url!r}")
    host = parsed.netloc.lower().split("@")[-1]
    if host.endswith(":80") and parsed.scheme == "http":
        host = host[:-3]
    if host.endswith(":443") and parsed.scheme == "https":
        host = host[:-4]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query = urlencode(sorted((key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() not in _TRACKING))
    return urlunsplit((parsed.scheme.lower(), host, path, query, ""))


def article_identity(url: str) -> str:
    """Stable ID for one normalized article identity."""
    return "article_" + sha256(normalize_url(url).encode("utf-8")).hexdigest()[:24]


def first_seen_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
            try:
                result = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"unsupported GDELT timestamp: {value!r}")
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def article_from_gal(row: Mapping[str, Any], *, source_class: str = "news") -> Article:
    """Normalize one GAL row without requiring every provider field."""
    raw_url = str(row.get("url") or "").strip()
    canonical = normalize_url(str(row.get("canonical_url") or raw_url))
    first_seen = first_seen_timestamp(row.get("date") or row.get("first_seen_at"))
    published = first_seen_timestamp(row.get("published_at"))
    basis = "published_at" if published else ("source_date" if first_seen else "unknown")
    return Article(
        article_id=article_identity(canonical), canonical_url=canonical,
        raw_urls=[raw_url or canonical], outlet_id=row.get("outlet_id"),
        outlet_domain=(str(row.get("domain") or row.get("outlet_domain") or "").lower() or None),
        outlet_edition=row.get("edition"), language=row.get("lang") or row.get("language"),
        first_seen_at=first_seen, source_date=first_seen, published_at=published,
        date_basis=basis, title=row.get("title"), description=row.get("description") or row.get("desc"),
        publishing_geography=row.get("publishing_geography"), source_class=source_class,
    )


def build_gal_inventory_sql(*, gal_table: str = "gdelt-bq.gdeltv2.gal") -> str:
    _validate_table(gal_table)
    return f"""SELECT
  url, date, domain, outletName AS outlet_name, lang, title, `desc` AS description
FROM `{gal_table}`
WHERE DATE(date) BETWEEN @start_date AND @end_date
  AND lang IN UNNEST(@languages)
  AND domain IS NOT NULL AND url IS NOT NULL""".strip()


def build_gkg_enrichment_sql(
    *, gkg_table: str = "gdelt-bq.gdeltv2.gkg_partitioned",
    date_expression: str = "PARSE_DATE('%Y%m%d', SUBSTR(CAST(DATE AS STRING), 1, 8))",
) -> str:
    """Build a left-joinable GKG candidate scan with exact theme tokens.

    GKG entity columns are aggregated before a join so repeated entities cannot
    inflate article counts.  Project-specific relevance is resolved downstream.
    """
    _validate_table(gkg_table)
    return f"""SELECT
  DocumentIdentifier AS url,
  {date_expression} AS observation_day,
  ARRAY(SELECT DISTINCT TRIM(value) FROM UNNEST(SPLIT(COALESCE(V2Persons, ''), ';')) value WHERE TRIM(value) != '') AS persons,
  ARRAY(SELECT DISTINCT TRIM(value) FROM UNNEST(SPLIT(COALESCE(V2Organizations, ''), ';')) value WHERE TRIM(value) != '') AS organisations,
  ARRAY(SELECT DISTINCT TRIM(value) FROM UNNEST(SPLIT(COALESCE(V2Locations, ''), ';')) value WHERE TRIM(value) != '') AS locations,
  ARRAY(SELECT DISTINCT TRIM(value) FROM UNNEST(SPLIT(COALESCE(V2Themes, ''), ';')) value WHERE TRIM(value) != '') AS theme_codes
FROM `{gkg_table}`
WHERE _PARTITIONDATE BETWEEN @start_date AND @end_date
  AND {date_expression} BETWEEN @start_date AND @end_date
  AND DocumentIdentifier IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY DocumentIdentifier, {date_expression} ORDER BY {date_expression} DESC) = 1""".strip()


def build_gal_gkg_join_sql(
    *, gal_table: str = "gdelt-bq.gdeltv2.gal",
    gkg_table: str = "gdelt-bq.gdeltv2.gkg_partitioned",
) -> str:
    """Return a normalized inventory query with a non-dropping GKG join."""
    _validate_table(gal_table)
    _validate_table(gkg_table)
    return f"""WITH gal_inventory AS (
  SELECT url, date, domain, outletName AS outlet_name, lang, title, `desc` AS description
  FROM `{gal_table}`
  WHERE DATE(date) BETWEEN @start_date AND @end_date
    AND lang IN UNNEST(@languages)
    AND url IS NOT NULL
), gkg_enrichment AS (
  {build_gkg_enrichment_sql(gkg_table=gkg_table)}
)
SELECT gal.*, gkg.persons, gkg.organisations, gkg.locations, gkg.theme_codes
FROM gal_inventory AS gal
LEFT JOIN gkg_enrichment AS gkg
  ON LOWER(gal.url) = LOWER(gkg.url)
 AND DATE(gal.date) = gkg.observation_day""".strip()


def _validate_table(identifier: str) -> None:
    if not _TABLE.fullmatch(identifier):
        raise ValueError(f"invalid BigQuery table identifier: {identifier!r}")


def evidence_by_article(evidence: Iterable[TagEvidence]) -> dict[str, list[TagEvidence]]:
    grouped: dict[str, list[TagEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.article_id].append(item)
    return dict(grouped)


def resolve_tag_assertions(
    assertions: Iterable[ArticleTagAssertion], *, resolution_version: str,
) -> list[ArticleTag]:
    """Resolve method assertions while retaining conflicts for review.

    Any positive assertion wins the resolved label, but a positive/negative
    conflict remains ``unknown``.  Unsupported/insufficient assertions do not
    silently become negative.
    """
    grouped: dict[tuple[str, str, str], list[ArticleTagAssertion]] = defaultdict(list)
    for assertion in assertions:
        grouped[(assertion.article_id, assertion.tag_id, assertion.assertion_type)].append(assertion)
    resolved: list[ArticleTag] = []
    for (article_id, tag_id, assertion_type), rows in sorted(grouped.items()):
        values = {row.result for row in rows if row.evaluation_status == EvaluationStatus.evaluated}
        if "present" in values and "absent" in values:
            result, status = "unknown", EvaluationStatus.insufficient_evidence
        elif "present" in values:
            result, status = "present", EvaluationStatus.evaluated
        elif "absent" in values:
            result, status = "absent", EvaluationStatus.evaluated
        else:
            result, status = "unknown", EvaluationStatus.insufficient_evidence
        resolved.append(ArticleTag(
            article_id=article_id, tag_id=tag_id, result=result,
            evaluation_status=status, tagging_version=max(r.tagging_version for r in rows),
            resolution_version=resolution_version,
            assertion_type=assertion_type,
            assertion_ids=[f"{r.article_id}:{r.tag_id}:{r.method}" for r in rows],
        ))
    return resolved


def build_daily_metrics(
    *, release_id: str, reporting_day: date, universe_article_ids: Iterable[str],
    tags: Iterable[ArticleTag], tag_id: str, tagging_version: str,
    event_article_ids: Iterable[str] | None = None, event_id: str | None = None,
    filter_definition: str = "", assertion_type: str = "mentions_theme",
) -> list[DailyMetric]:
    """Return count, coverage and evaluable-share metrics with null zero-denoms."""
    universe = set(universe_article_ids)
    event_ids = set(event_article_ids or ())
    event_filter = event_id is not None or event_article_ids is not None
    relevant = universe & event_ids if event_filter else universe
    rows = {tag.article_id: tag for tag in tags if tag.tag_id == tag_id and tag.assertion_type == assertion_type and tag.article_id in relevant}
    evaluable = {aid for aid, tag in rows.items() if tag.evaluation_status == EvaluationStatus.evaluated}
    positives = {aid for aid in evaluable if rows[aid].result == "present"}
    unknown = len(relevant - evaluable)
    denominator = len(relevant)
    coverage = len(evaluable) / denominator if denominator else None
    share = len(positives) / len(evaluable) if evaluable else None
    common = dict(release_id=release_id, reporting_day=reporting_day, tag_id=tag_id,
                  event_id=(event_id if event_filter else None), universe_count=denominator,
                  evaluable_count=len(evaluable), positive_count=len(positives), unknown_count=unknown,
        filter_definition=filter_definition or f"{assertion_type}; " + ("event subset" if event_filter else "captured UK outlet universe"),
                  tagging_version=tagging_version)
    return [
        DailyMetric(metric_name="tagged_article_count", value=float(len(positives)), **common),
        DailyMetric(metric_name="analysis_coverage", value=coverage, **common),
        DailyMetric(metric_name="theme_share_within_event" if event_filter else "theme_share_among_evaluable", value=share, **common),
    ]


def build_capture_membership_digest(memberships: Sequence[CaptureMembership]) -> str:
    payload = "\n".join(f"{item.reporting_day.isoformat()}\t{item.article_id}\t{int(item.included)}" for item in sorted(memberships, key=lambda x: (x.reporting_day, x.article_id)))
    return sha256(payload.encode("utf-8")).hexdigest()


def build_capture_manifest(
    *, snapshot_id: str, source: str, requested_start: date, requested_end: date,
    memberships: Sequence[CaptureMembership], outlet_registry_version: str,
    language_scope: Sequence[str] = ("en",), generated_at: datetime | None = None,
):
    from .contracts import CaptureManifest
    included = [item for item in memberships if item.included]
    return CaptureManifest(
        snapshot_id=snapshot_id, source=source, requested_start=requested_start,
        requested_end=requested_end, language_scope=list(language_scope),
        outlet_registry_version=outlet_registry_version,
        membership_digest=build_capture_membership_digest(memberships),
        article_count=len({item.article_id for item in included}),
        excluded_count=sum(not item.included for item in memberships),
        ambiguous_count=sum(item.reason == "ambiguous" for item in memberships),
        generated_at=generated_at or datetime.now(timezone.utc),
    )


def candidate_event_links(
    *, article: Article, aliases: Mapping[str, Sequence[str]],
    text: str, event_type: str, linker_version: str = "event-linker-v1",
) -> list[ArticleEventLink]:
    """Produce reviewable event candidates from aliases and hazard context.

    An alias hit is a candidate until contextual review resolves it.  Unnamed
    hazard candidates require hazard language; a location/date match alone is
    intentionally not promoted to a confirmed event link.
    """
    haystack = text.casefold()
    hazard_terms = {"storm", "flood", "wildfire", "fire", "cyclone", "hurricane"}
    links: list[ArticleEventLink] = []
    for event_id, values in aliases.items():
        matched = next((alias for alias in values if alias.casefold() in haystack), None)
        if not matched:
            continue
        evidence_id = "ev_" + sha256(f"{article.article_id}:{event_id}:{matched}".encode()).hexdigest()[:20]
        links.append(ArticleEventLink(
            article_id=article.article_id, event_id=event_id, relation="current",
            evidence_ids=[evidence_id], method="alias", resolution_status="ambiguous",
            linker_version=linker_version,
        ))
    if not links and event_type.casefold() in hazard_terms and any(term in haystack for term in hazard_terms):
        links.append(ArticleEventLink(
            article_id=article.article_id, event_id=None, relation="candidate",
            evidence_ids=[], method="location_time", resolution_status="unresolved",
            linker_version=linker_version,
        ))
    return links


def coverage_rows_for_articles(
    articles: Iterable[Article], *, tag_family: str, tagging_version: str,
    available_text_scope: str = "GAL metadata and retained NGrams evidence",
) -> list[ClassificationCoverage]:
    """Create explicit coverage rows so absent assertions never imply negatives."""
    return [ClassificationCoverage(
        article_id=article.article_id, tag_family=tag_family,
        evaluation_status=EvaluationStatus.not_evaluated,
        available_text_scope=available_text_scope, tagging_version=tagging_version,
    ) for article in articles]
