"""Versioned contracts for the UK Attention Atlas serving and research layers.

These contracts intentionally keep source-specific measures separate. A missing
observation is represented by ``status='missing'`` or ``status='outage'`` and is
never silently converted to zero.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QualityStatus(StrEnum):
    observed = "observed"
    missing = "missing"
    outage = "outage"
    unsupported = "unsupported"
    partial = "partial"


class TopicDefinition(Contract):
    schema_version: Literal[1] = 1
    topic_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    enabled: bool = True
    language: str = Field(min_length=2, max_length=8)
    translation_status: Literal["draft", "reviewed", "validated"] = "draft"
    phrases: list[str] = Field(min_length=1)
    notes: str
    configuration_version: str = "uk-pilot-v1"
    language_gaps: list[str] = Field(default_factory=list)

    @field_validator("phrases")
    @classmethod
    def unique_phrases(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("phrases must be non-empty and unique")
        return cleaned


class OutletRegistryEntry(Contract):
    outlet_id: str
    domain: str
    outlet_name: str
    country: str = "GB"
    classification: Literal["national", "regional", "public_service", "trade", "other"]
    reviewed: bool = False
    edition: str | None = None
    domain_aliases: list[str] = Field(default_factory=list)
    publishing_geography: str | None = None
    coverage_areas: list[str] = Field(default_factory=list)
    source_class: Literal["news", "official", "parliamentary", "party", "other"] = "news"
    registry_version: str = "uk-outlets-v1"


class AccountPanelEntry(Contract):
    account_id: str
    did: str = Field(min_length=5)
    handle: str
    display_name: str
    category: Literal["politician", "organisation", "journalist", "commentator", "transport", "climate"]
    country: str = "GB"
    review_status: Literal["seed", "reviewed", "excluded"] = "seed"


class ArticleRecord(Contract):
    schema_version: Literal[1] = 1
    article_id: str
    url: str
    canonical_url: str | None = None
    published_at: datetime
    title: str | None = None
    outlet_domain: str | None = None
    outlet_classification: str | None = None
    topic_id: str
    phrase_evidence: list[str] = Field(default_factory=list)
    source: str = "gdelt_ngrams"
    publishing_geography: str = "GB"
    mentioned_geography: str | None = None
    configuration_version: str
    collection_run_id: str
    retrieval_status: Literal["metadata_only", "retrieved", "unavailable"] = "metadata_only"
    observed_at: datetime
    collected_at: datetime
    release_id: str
    quality_status: QualityStatus = QualityStatus.observed


# Article-level GDELT pipeline contracts.  These are deliberately source
# neutral: GAL, Web NGrams and GKG observations are retained separately and
# resolved tags are produced by a versioned tagging run.
class EvaluationStatus(StrEnum):
    evaluated = "evaluated"
    insufficient_evidence = "insufficient_evidence"
    not_evaluated = "not_evaluated"
    failed = "failed"
    unsupported = "unsupported"


class Article(Contract):
    schema_version: Literal[1] = 1
    article_id: str
    canonical_url: str
    raw_urls: list[str] = Field(min_length=1)
    outlet_id: str | None = None
    outlet_domain: str | None = None
    outlet_edition: str | None = None
    language: str | None = None
    first_seen_at: datetime | None = None
    source_date: datetime | None = None
    published_at: datetime | None = None
    date_basis: Literal["first_seen_utc", "source_date", "published_at", "unknown"] = "unknown"
    title: str | None = None
    description: str | None = None
    publishing_geography: str | None = None
    source_class: Literal["news", "official", "parliamentary", "party", "other"] = "news"


class ArticleSourceSnapshot(Contract):
    article_id: str
    source: Literal["gal", "webngrams", "gkg", "events", "other"]
    source_record_id: str | None = None
    raw_reference: str | None = None
    retrieved_at: datetime
    source_version: str | None = None
    status: Literal["available", "partial", "missing", "outage", "access_pending"] = "available"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaptureMembership(Contract):
    snapshot_id: str
    article_id: str
    reporting_day: date
    included: bool = True
    reason: str | None = None


class TagDefinition(Contract):
    tag_id: str
    label: str
    family: Literal["theme", "event_category", "political", "other"]
    definition: str
    hierarchy: str | None = None
    language: str = "en"
    aliases: list[str] = Field(default_factory=list)
    phrases: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    gkg_theme_codes: list[str] = Field(default_factory=list)
    status: Literal["draft", "reviewed", "validated"] = "draft"
    catalog_version: str


class ArticleTagAssertion(Contract):
    article_id: str
    tag_id: str
    method: Literal["phrase", "gkg", "title_description", "manual", "event_link", "other"]
    assertion_type: Literal["mentions_theme", "about_theme", "links_event_to_theme"] = "mentions_theme"
    result: Literal["present", "absent", "unknown"]
    evaluation_status: EvaluationStatus
    tagging_version: str
    evidence_ids: list[str] = Field(default_factory=list)
    rule_hash: str


class ArticleTag(Contract):
    article_id: str
    tag_id: str
    result: Literal["present", "absent", "unknown"]
    evaluation_status: EvaluationStatus
    tagging_version: str
    resolution_version: str
    assertion_type: Literal["mentions_theme", "about_theme", "links_event_to_theme"] = "mentions_theme"
    assertion_ids: list[str] = Field(default_factory=list)


class TagEvidence(Contract):
    evidence_id: str
    article_id: str
    source: Literal["webngrams", "gkg", "gal", "manual", "event_registry", "other"]
    source_record_id: str | None = None
    phrase: str | None = None
    context: str | None = None
    source_field: str | None = None
    position_decile: int | None = Field(default=None, ge=0, le=9)
    truncated: bool = False
    captured_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entity(Contract):
    entity_id: str
    entity_type: Literal["actor", "party", "policy"]
    canonical_name: str
    roles: list[str] = Field(default_factory=list)
    party_affiliations: list[str] = Field(default_factory=list)
    valid_from: date | None = None
    valid_to: date | None = None
    source_urls: list[str] = Field(default_factory=list)


class EntityAlias(Contract):
    entity_id: str
    alias: str
    language: str = "en"
    valid_from: date | None = None
    valid_to: date | None = None


class Event(Contract):
    event_id: str
    canonical_name: str
    event_type: str
    aliases: list[str] = Field(default_factory=list)
    start_at: datetime | None = None
    end_at: datetime | None = None
    geometry: dict[str, Any] | None = None
    geography_ids: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list)
    registry_version: str


class EventAlias(Contract):
    event_id: str
    alias: str
    normalized_alias: str | None = None


class ArticleEventLink(Contract):
    article_id: str
    event_id: str | None = None
    relation: Literal["current", "retrospective", "candidate"]
    evidence_ids: list[str] = Field(default_factory=list)
    method: Literal["alias", "location_time", "manual", "external_feed"]
    resolution_status: Literal["resolved", "ambiguous", "unresolved"]
    linker_version: str


class Place(Contract):
    place_id: str
    name: str
    provider_id: str | None = None
    code_system: str | None = None
    country_code: str | None = None
    geometry: dict[str, Any] | None = None
    boundary_version: str | None = None


class ArticleLocation(Contract):
    article_id: str
    place_id: str | None = None
    raw_name: str
    role: Literal["publication_base", "outlet_coverage_area", "mentioned_place", "event_location", "article_focus"]
    resolution_method: str
    ambiguity: str | None = None


class ClassificationCoverage(Contract):
    article_id: str
    tag_family: str
    evaluation_status: EvaluationStatus
    available_text_scope: str
    failure_reason: str | None = None
    tagging_version: str


class DailyMetric(Contract):
    release_id: str
    reporting_day: date
    tag_id: str | None = None
    event_id: str | None = None
    universe_count: int = Field(ge=0)
    evaluable_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    metric_name: Literal["tagged_article_count", "analysis_coverage", "theme_share_among_evaluable", "theme_share_within_event", "event_theme_evaluation_coverage"]
    value: float | None = None
    filter_definition: str
    tagging_version: str

    @model_validator(mode="after")
    def counts_reconcile(self) -> "DailyMetric":
        if self.evaluable_count > self.universe_count:
            raise ValueError("evaluable_count cannot exceed universe_count")
        if self.positive_count > self.evaluable_count:
            raise ValueError("positive_count cannot exceed evaluable_count")
        if self.unknown_count != self.universe_count - self.evaluable_count:
            raise ValueError("unknown_count must reconcile to the denominator")
        if self.value is not None and self.metric_name in {"analysis_coverage", "theme_share_among_evaluable", "theme_share_within_event", "event_theme_evaluation_coverage"} and not 0 <= self.value <= 1:
            raise ValueError("share and coverage metrics must be between zero and one")
        return self


class CaptureManifest(Contract):
    snapshot_id: str
    source: Literal["gdelt_gal", "gdelt_ngrams", "gdelt_gkg", "combined"]
    requested_start: date
    requested_end: date
    language_scope: list[str] = Field(default_factory=lambda: ["en"])
    outlet_registry_version: str
    membership_digest: str
    article_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    generated_at: datetime


class ArticleMatchEvidence(Contract):
    article_id: str
    topic_id: str
    phrase: str
    language: str
    context: str | None = None
    classifier_version: str


class DailyAttention(Contract):
    schema_version: Literal[1] = 1
    date: date
    source: Literal["gdelt_ngrams", "bluesky", "google_trends", "junkipedia_mp"]
    topic_id: str
    measure: Literal["count", "share", "index"]
    value: float | None
    unit: Literal["articles", "share_of_captured_gdelt_news", "posts", "share_of_monitored_panel_posts", "index_0_100"]
    denominator: float | None = None
    denominator_definition: str
    geography: str = "GB"
    quality_status: QualityStatus = QualityStatus.observed
    completeness: float | None = Field(default=None, ge=0, le=1)
    observed_at: datetime | None = None
    collected_at: datetime
    release_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def denominator_required_for_share(self) -> "DailyAttention":
        if self.measure == "share" and (self.denominator is None or self.value is None):
            raise ValueError("share observations require numerator and denominator")
        return self


class DailyNewsDenominator(Contract):
    date: date
    source: Literal["gdelt_ngrams"] = "gdelt_ngrams"
    geography: str = "GB"
    captured_article_count: int = Field(ge=0)
    captured_url_manifest: dict[str, Any]
    capture_universe_hash: str = Field(min_length=12)
    definition: str = "distinct captured GDELT UK news URLs"
    quality_status: QualityStatus = QualityStatus.observed
    release_id: str


class SocialPost(Contract):
    schema_version: Literal[1] = 1
    post_id: str
    account_did: str
    handle: str
    post_uri: str
    posted_at: datetime
    text: str | None = None
    topic_ids: list[str] = Field(default_factory=list)
    deleted: bool = False
    updated: bool = False
    cursor: str | None = None
    source: Literal["bluesky_appview", "bluesky_jetstream"] = "bluesky_appview"
    collection_run_id: str
    release_id: str
    quality_status: QualityStatus = QualityStatus.observed


class SearchInterest(Contract):
    date: date
    topic_id: str
    value: float | None
    unit: Literal["index_0_100"] = "index_0_100"
    source: Literal["google_trends_official", "google_trends_experimental"]
    geography: str = "GB"
    quality_status: QualityStatus = QualityStatus.missing
    release_id: str


class EventRecord(Contract):
    schema_version: Literal[1] = 1
    event_id: str
    source: Literal["gdacs", "firms", "custom"]
    event_type: str
    name: str
    start_at: datetime
    end_at: datetime | None = None
    geography_ids: list[str] = Field(default_factory=list)
    country_codes: list[str] = Field(default_factory=lambda: ["GB"])
    alert_level: str | None = None
    source_url: str | None = None
    geometry: dict[str, Any] | None = None
    quality_status: QualityStatus = QualityStatus.observed
    release_id: str


class PhysicalObservation(Contract):
    schema_version: Literal[1] = 1
    observation_id: str
    source: str
    metric: str
    observed_at: date
    geography: str = "GB"
    value: float | None
    unit: str
    baseline_start_year: int | None = None
    baseline_end_year: int | None = None
    valid_area_fraction: float | None = Field(default=None, ge=0, le=1)
    quality_status: QualityStatus = QualityStatus.observed
    release_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationRecord(Contract):
    """Provider-neutral observation for prices, weather, disruption and indices."""

    schema_version: Literal[1] = 1
    observation_id: str
    source: str
    series_id: str
    metric: str
    observed_at: date
    geography: str = "GB"
    geography_level: Literal["country", "nation", "region", "local_authority", "station", "market"] = "country"
    value: float | None
    unit: str
    quality_status: QualityStatus = QualityStatus.observed
    completeness: float | None = Field(default=None, ge=0, le=1)
    revision_status: Literal["initial", "revised", "final", "not_applicable"] = "not_applicable"
    collection_run_id: str
    collected_at: datetime
    release_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceSnapshot(Contract):
    """Evidence that a source was checked, including gaps and provider limits."""

    schema_version: Literal[1] = 1
    source: str
    snapshot_id: str
    status: Literal["fixture", "available", "partial", "missing", "outage", "access_pending"]
    observed_start: date | None = None
    observed_end: date | None = None
    retrieved_at: datetime
    endpoint: str | None = None
    request_count: int = Field(default=0, ge=0)
    rate_limit_note: str | None = None
    completeness: float | None = Field(default=None, ge=0, le=1)
    notes: str
    release_id: str


class DataLayerDefinition(Contract):
    """Operational registry entry for a planned or available source layer."""

    schema_version: Literal[1] = 1
    layer_id: str
    label: str
    provider: str
    cadence: Literal["daily", "weekly", "monthly", "triannual", "event_driven", "on_demand"]
    geography: str
    units: list[str] = Field(min_length=1)
    status: Literal["fixture_ready", "adapter_ready", "access_pending", "deferred"]
    source_url: str | None = None
    access_requirement: str
    independence_note: str
    release_id: str


class RunManifest(Contract):
    schema_version: Literal[1] = 1
    run_id: str
    source: str
    status: Literal["planned", "running", "success", "partial", "failed"]
    requested_start: date
    requested_end: date
    configuration_version: str
    configuration_hash: str
    records_written: int = Field(ge=0)
    missing_dates: list[date] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    finished_at: datetime | None = None


class DatasetRelease(Contract):
    schema_version: Literal[1] = 1
    release_id: str
    created_at: datetime
    date_start: date
    date_end: date
    configuration_version: str
    configuration_hash: str
    configuration_files: dict[str, str] = Field(default_factory=dict)
    source_snapshots: dict[str, str]
    parquet_outputs: list[str]
    supabase_rows: dict[str, int]
    frontend_assets: list[str]
    status: Literal["fixture", "candidate", "published", "rolled_back"] = "fixture"
    methodology_note: str = "Associations and timing are exploratory; this release does not establish causality."
    content_hash: str = ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
