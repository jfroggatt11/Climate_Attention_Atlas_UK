"""Deterministic local vertical slice and release export helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import config_hash, load_config
from .contracts import (
    ArticleRecord,
    DatasetRelease,
    DailyAttention,
    DailyNewsDenominator,
    EventRecord,
    PhysicalObservation,
    SocialPost,
    utc_now,
)
from .panel import load_account_panel, load_outlet_registry
from .source_layers import build_layer_fixture


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"


def _stable(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _dt(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def build_fixture(start: date = date(2026, 8, 1), end: date = date(2026, 8, 30)) -> dict[str, Any]:
    """Build small, deterministic records with real contract validation."""
    topic_cfg = load_config(CONFIG / "topics.uk-pilot.yaml")
    outlets = load_outlet_registry(CONFIG / "outlet_registry.yaml")
    accounts = load_account_panel(CONFIG / "account_panel.yaml")
    config_sha = config_hash(CONFIG / "topics.uk-pilot.yaml")
    run_id = "fixture-run-2026-09-23"
    release_id = "uk-atlas-fixture-2026-09-23"
    topics = [
        (topic.id, topic.label, [p.text for p in topic.ngram_phrases[:3]])
        for topic in topic_cfg.topics
    ]
    articles: list[dict[str, Any]] = []
    news: list[dict[str, Any]] = []
    denominators: list[dict[str, Any]] = []
    posts: list[dict[str, Any]] = []
    physical: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for index, day in enumerate(_date_range(start, end)):
        denominator = 880 + (index * 17) % 140
        denominators.append(DailyNewsDenominator(
            date=day, captured_article_count=denominator, release_id=release_id
        ).model_dump(mode="json"))
        for topic_index, (topic_id, label, phrases) in enumerate(topics):
            # A smooth deterministic series with an event-linked bump, useful for UI smoke tests.
            base = 24 + topic_index * 11 + (index * (topic_index + 3)) % 22
            bump = 32 if 12 <= index <= 15 and topic_id in {"climate_change", "clean_transport"} else 0
            count = base + bump
            news.append(DailyAttention(
                date=day, source="gdelt_ngrams", topic_id=topic_id, measure="share",
                value=round(count / denominator, 5), unit="share_of_captured_gdelt_news",
                denominator=denominator, denominator_definition="distinct captured GDELT UK news URLs",
                completeness=1.0, observed_at=_dt(day), collected_at=_dt(day, 13), release_id=release_id,
                metadata={"raw_article_count": count, "source_scope": "UK publishing geography"},
            ).model_dump(mode="json"))
            if index % 3 != 0:  # sparse article evidence sample, while daily totals remain complete
                article_id = f"art_{_stable(f'{day}-{topic_id}')}"
                outlet = outlets[(index + topic_index) % len(outlets)]
                phrase = phrases[index % len(phrases)]
                articles.append(ArticleRecord(
                    article_id=article_id, url=f"https://{outlet.domain}/uk-atlas-fixture/{article_id}",
                    canonical_url=f"https://{outlet.domain}/uk-atlas-fixture/{article_id}", published_at=_dt(day, 8 + topic_index),
                    title=f"{label}: monitored fixture article", outlet_domain=outlet.domain,
                    outlet_classification=outlet.classification, topic_id=topic_id, phrase_evidence=[phrase],
                    configuration_version="uk-pilot-v1", collection_run_id=run_id, observed_at=_dt(day),
                    collected_at=_dt(day, 13), release_id=release_id,
                ).model_dump(mode="json"))
        # Bluesky is a separate monitored-panel denominator, never mixed with news.
        panel_total = 18 + index % 5
        for account_index, account in enumerate(accounts[: min(len(accounts), 3)]):
            if (index + account_index) % 2 == 0:
                topic_id = topics[(index + account_index) % len(topics)][0]
                posts.append(SocialPost(
                    post_id=f"post_{_stable(f'{day}-{account.account_id}')}", account_did=account.did,
                    handle=account.handle, post_uri=f"at://{account.did}/app.bsky.feed.post/{_stable(str(day))}",
                    posted_at=_dt(day, 9 + account_index), text=f"Fixture post about {topic_id.replace('_', ' ')}",
                    topic_ids=[topic_id], cursor=f"cursor-{day.isoformat()}", collection_run_id=run_id,
                    release_id=release_id,
                ).model_dump(mode="json"))
        for topic_index, (topic_id, _, _) in enumerate(topics):
            topic_posts = sum(topic_id in post["topic_ids"] for post in posts if post["posted_at"].startswith(day.isoformat()))
            news.append(DailyAttention(
                date=day, source="bluesky", topic_id=topic_id, measure="share",
                value=round(topic_posts / panel_total, 5), unit="share_of_monitored_panel_posts",
                denominator=panel_total, denominator_definition="posts from monitored Bluesky accounts",
                completeness=0.85, observed_at=_dt(day), collected_at=_dt(day, 14), release_id=release_id,
                metadata={"raw_post_count": topic_posts, "panel_accounts": len(accounts), "panel_status": "seed"},
            ).model_dump(mode="json"))
        # Monthly MODIS is represented once in this compact demo; only first day of month is used here.
        if day.day == 1:
            physical.append(PhysicalObservation(
                observation_id="modis_gb_2026-08", source="modis_mod13c2", metric="ndvi_anomaly",
                observed_at=day, value=0.08, unit="index_anomaly", baseline_start_year=2001,
                baseline_end_year=2020, valid_area_fraction=0.91, release_id=release_id,
                metadata={"product": "MOD13C2.061", "period": "2026-08", "geography_definition": "UK country-scale 0.05-degree valid cells"},
            ).model_dump(mode="json"))
    events.append(EventRecord(
        event_id="gdacs-uk-demo-01", source="gdacs", event_type="wildfire", name="UK summer wildfire context",
        start_at=_dt(start + timedelta(days=12)), end_at=_dt(start + timedelta(days=16)), geography_ids=["GB"],
        alert_level="Orange", source_url="https://www.gdacs.org/", release_id=release_id,
        geometry={"type": "Point", "coordinates": [-1.5, 52.5]},
    ).model_dump(mode="json"))
    events.append(EventRecord(
        event_id="firms-uk-demo-01", source="firms", event_type="active_fire", name="FIRMS active-fire context",
        start_at=_dt(start + timedelta(days=13)), end_at=_dt(start + timedelta(days=14)), geography_ids=["GB"],
        source_url="https://firms.modaps.eosdis.nasa.gov/", release_id=release_id,
        geometry={"type": "Point", "coordinates": [-2.1, 53.0]},
    ).model_dump(mode="json"))
    layer_data = build_layer_fixture(start, end)
    layer_snapshots = {item["source"]: item["snapshot_id"] for item in layer_data["source_snapshots"]}
    return {
        "release": DatasetRelease(
            release_id=release_id, created_at=utc_now(), date_start=start, date_end=end,
            configuration_version="uk-pilot-v1", configuration_hash=config_sha,
            source_snapshots={"gdelt_ngrams": "fixture-v1", "bluesky": "seed-panel-fixture-v1", "modis_mod13c2": "imported-fixture-v1", "gdacs": "fixture-v1", "firms": "fixture-v1", **layer_snapshots},
            parquet_outputs=["data/processed/daily_attention.parquet", "data/processed/article_records.parquet", "data/processed/layer_observations.parquet"],
            supabase_rows={"daily_attention": len(news), "article_records": len(articles), "events": len(events), "physical_observations": len(physical), "layer_observations": len(layer_data["observations"])},
            frontend_assets=["frontend/public/data/release.json"], status="fixture",
        ).model_dump(mode="json"),
        "daily_attention": news, "news_denominators": denominators, "articles": articles,
        "social_posts": posts, "physical_observations": physical, "events": events,
        "metadata": {"topic_count": len(topics), "panel_accounts": len(accounts), "panel_definition": "seed monitored accounts; not UK social attention", "article_denominator": "distinct captured GDELT UK news URLs"},
        "data_layers": layer_data["observations"], "source_snapshots": layer_data["source_snapshots"],
        "layer_definitions": layer_data["layer_definitions"],
    }


def write_json(data: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def export_frontend(data: dict[str, Any], output: str | Path) -> Path:
    destination = write_json(data, output)
    return destination


def quality_report(data: dict[str, Any]) -> dict[str, Any]:
    daily = data.get("daily_attention", [])
    ids = [item.get("date", "") + item.get("source", "") + item.get("topic_id", "") for item in daily]
    duplicates = len(ids) - len(set(ids))
    missing_share_denominators = [item for item in daily if item.get("measure") == "share" and not item.get("denominator")]
    return {"daily_rows": len(daily), "duplicate_daily_keys": duplicates, "missing_share_denominators": len(missing_share_denominators), "article_rows": len(data.get("articles", [])), "social_rows": len(data.get("social_posts", [])), "event_rows": len(data.get("events", [])), "physical_rows": len(data.get("physical_observations", [])), "status": "pass" if duplicates == 0 and not missing_share_denominators else "fail"}
