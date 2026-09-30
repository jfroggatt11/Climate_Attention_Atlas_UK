from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from climate_attention.article_pipeline import (
    estimate_article_pipeline,
    prepare_gkg_query,
    run_article_pipeline,
    validate_article_release,
)
from climate_attention.validation import build_article_validation_sample, score_article_validation


class FakeExecutor:
    def estimate(self, sql, parameters):
        return 1

    def query(self, sql, parameters, *, maximum_bytes_billed):
        if "gkg_partitioned" in sql:
            return ([{
                "url": "https://bbc.co.uk/story",
                "observation_day": date(2026, 8, 1),
                "persons": ["Jane Doe"],
                "organisations": [],
                "locations": ["London"],
                "theme_codes": ["ENV_CLIMATECHANGE"],
            }], {"total_bytes_billed": 1})
        if "article_samples_json" not in sql:
            return ([{
                "url": "https://bbc.co.uk/story",
                "date": "20260801000000",
                "domain": "bbc.co.uk",
                "lang": "en",
                "title": "Climate story",
                "desc": "Example",
            }], {"total_bytes_billed": 1})
        topics = [
            "climate_change", "fuel_prices", "clean_transport",
            "electric_vehicles", "extreme_weather", "event_storm", "event_flood", "event_wildfire",
        ]
        rows = []
        for topic in topics:
            rows.append({
                "topic_id": topic,
                "day": date(2026, 8, 1),
                "country_id": "unitedkingdom",
                "matched_count": 1,
                "monitored_count": 1,
                "political_count": 0,
                "political_actor_count": 0,
                "government_action_count": 0,
                "party_politics_count": 0,
                "official_source_count": 0,
                "article_samples_json": json.dumps([{
                    "url": "https://bbc.co.uk/story", "domain": "bbc.co.uk",
                    "published_at": "2026-08-01T00:00:00+00:00", "title": "Climate story",
                    "description": "Example", "lang": "en",
                    "match_evidence": [{
                        "evidence_kind": "topic", "dimension_id": topic,
                        "phrase": topic.replace("_", " "), "phrase_language": "en",
                        "segmentation": "space", "context": topic,
                    }],
                }]),
                "language_counts_json": "[]",
                "total_matched_urls": 1,
                "attributed_matched_urls": 1,
                "mapped_domain_count": 1,
            })
        return rows, {"total_bytes_billed": 1}


def test_gkg_query_is_url_bounded():
    sql, params = prepare_gkg_query(
        start=date(2026, 8, 1), end=date(2026, 8, 1), article_urls=["https://bbc.co.uk/story"]
    )
    assert "_PARTITIONDATE BETWEEN @start_date AND @end_date" in sql
    assert "DocumentIdentifier IN UNNEST(@article_urls)" in sql
    assert params["article_urls"] == ["https://bbc.co.uk/story"]


def test_article_pipeline_writes_candidate_release(tmp_path: Path):
    output = run_article_pipeline(
        start=date(2026, 8, 1), end=date(2026, 8, 1), billing_project="test-project",
        maximum_bytes_billed=10, run_id="test-run", data_root=tmp_path,
        executor=FakeExecutor(), gkg_enabled=True,
    )
    payload = json.loads(output.read_text())
    assert payload["status"] == "candidate"
    assert payload["capture_manifest"]["article_count"] == 1
    assert payload["tag_evidence"]
    assert payload["source_jobs"]["gkg"]["total_bytes_billed"] == 1
    assert all(Path(path).exists() for path in payload["parquet_outputs"])
    assert validate_article_release(payload) == []
    assert run_article_pipeline(
        start=date(2026, 8, 1), end=date(2026, 8, 1), billing_project="test-project",
        maximum_bytes_billed=10, run_id="test-run", data_root=tmp_path,
        executor=FakeExecutor(), gkg_enabled=True,
    ) == output


def test_article_pipeline_estimate_is_non_billable_with_fake_executor():
    estimate = estimate_article_pipeline(
        start=date(2026, 8, 1), end=date(2026, 8, 1), billing_project="test-project",
        maximum_bytes_billed=10, executor=FakeExecutor(),
    )
    assert estimate["billable"] is False
    assert estimate["inventory_estimated_bytes"] == 1
    assert estimate["ngram_windows"]


def test_validation_sample_includes_unmatched_inventory_rows():
    rows = build_article_validation_sample(
        [
            {"article_id": "a", "canonical_url": "https://example/a", "candidate_tag_ids": []},
            {"article_id": "b", "canonical_url": "https://example/b", "candidate_tag_ids": ["climate_change"]},
        ],
        tag_ids=["climate_change"], sample_size=2,
    )
    assert {row["article_id"] for row in rows} == {"a", "b"}
    assert rows[0]["labels"]["climate_change"] is None


def test_validation_scoring_reports_precision_recall_intervals():
    report = score_article_validation([
        {"candidate_tag_ids": ["climate_change"], "labels": {"climate_change": True}},
        {"candidate_tag_ids": ["climate_change"], "labels": {"climate_change": False}},
        {"candidate_tag_ids": [], "labels": {"climate_change": True}},
    ], tag_ids=["climate_change"])
    assert report["climate_change"]["precision"] == 0.5
    assert report["climate_change"]["recall"] == 0.5
    assert len(report["climate_change"]["precision_wilson_95"]) == 2
