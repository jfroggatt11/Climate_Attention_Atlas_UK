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
    source: Literal["gdelt_ngrams", "bluesky", "google_trends"]
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
    source: Literal["modis_mod13c2", "modis_mcd64", "firms", "haduk_grid", "environment_agency"]
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
    source_snapshots: dict[str, str]
    parquet_outputs: list[str]
    supabase_rows: dict[str, int]
    frontend_assets: list[str]
    status: Literal["fixture", "candidate", "published", "rolled_back"] = "fixture"
    methodology_note: str = "Associations and timing are exploratory; this release does not establish causality."


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
