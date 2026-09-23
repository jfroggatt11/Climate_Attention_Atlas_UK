from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from climate_attention.contracts import DailyAttention, QualityStatus, TopicDefinition


def test_topic_definition_records_draft_language_status_and_gaps():
    topic = TopicDefinition(
        topic_id="electric_vehicles",
        label="Electric vehicles",
        language="en",
        phrases=["electric vehicle"],
        notes="Seed phrase list for review.",
        language_gaps=["cy", "gd"],
    )
    assert topic.translation_status == "draft"
    assert topic.language_gaps == ["cy", "gd"]


def test_share_requires_aligned_denominator():
    with pytest.raises(ValidationError):
        DailyAttention(
            date=date(2026, 8, 1), source="gdelt_ngrams", topic_id="climate_change",
            measure="share", value=0.1, unit="share_of_captured_gdelt_news",
            denominator_definition="same-day captured news", collected_at=datetime.now(timezone.utc),
            release_id="test",
        )


def test_missing_is_not_zero():
    item = DailyAttention(
        date=date(2026, 8, 1), source="bluesky", topic_id="climate_change",
        measure="count", value=None, unit="posts", denominator_definition="monitored panel",
        quality_status=QualityStatus.missing, collected_at=datetime.now(timezone.utc), release_id="test",
    )
    assert item.value is None
    assert item.quality_status == QualityStatus.missing
