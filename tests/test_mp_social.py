from datetime import datetime, timezone

import pytest

from climate_attention.sources.mp_social import import_mp_social_rows


HEADERS = [
    "level", "category", "grain", "period", "party", "platform", "posts",
    "likes_sum", "likes_posts", "shares_sum", "shares_posts",
]


def test_mp_import_aggregates_posts_and_ignores_engagement():
    rows = [
        HEADERS,
        ["party", "fuel_prices", "day", "2026-09-01", "Labour", "x_twitter", "2", "-1", "2", "4", "2"],
        ["party", "fuel_prices", "day", "2026-09-01", "Conservative", "facebook", "3", "10", "3", "2", "3"],
        ["party", "fuel_prices", "month", "2026-09", "Labour", "x_twitter", "2", "", "", "", ""],
        ["party", "fuel_prices", "month", "2026-09", "Conservative", "facebook", "3", "", "", "", ""],
        ["party", "fuel_prices", "year", "2026", "Labour", "x_twitter", "2", "", "", "", ""],
        ["party", "fuel_prices", "year", "2026", "Conservative", "facebook", "3", "", "", "", ""],
    ]
    result = import_mp_social_rows(
        rows,
        release_id="release-1",
        collection_run_id="run-1",
        collected_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    assert len(result["daily_attention"]) == 1
    record = result["daily_attention"][0]
    assert record["topic_id"] == "fuel_prices"
    assert record["value"] == 5.0
    assert record["metadata"]["party_breakdown"] == {"Conservative": 3, "Labour": 2}
    assert record["metadata"]["platform_breakdown"] == {"facebook": 3, "x_twitter": 2}
    assert result["metadata"]["engagement_fields_ignored"]


def test_mp_import_maps_evs_and_extreme_weather():
    rows = [
        HEADERS,
        ["party", "evs", "day", "2026-09-01", "Labour", "x_twitter", "1", "0", "1", "0", "1"],
        ["party", "extreme_weather", "day", "2026-09-01", "Labour", "x_twitter", "2", "0", "2", "0", "2"],
    ]
    result = import_mp_social_rows(rows, release_id="release-1", collection_run_id="run-1")
    assert {row["topic_id"] for row in result["daily_attention"]} == {"electric_vehicles", "extreme_weather"}


def test_mp_import_rejects_unreconciled_month():
    rows = [
        HEADERS,
        ["party", "fuel_prices", "day", "2026-09-01", "Labour", "x_twitter", "2", "", "", "", ""],
        ["party", "fuel_prices", "month", "2026-09", "Labour", "x_twitter", "3", "", "", "", ""],
    ]
    with pytest.raises(ValueError, match="month control does not reconcile"):
        import_mp_social_rows(rows, release_id="release-1", collection_run_id="run-1")
