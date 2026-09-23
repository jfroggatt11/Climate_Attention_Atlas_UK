"""Pre-publication audits that can run before provider access is granted."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .config import load_config, load_political_config
from .panel import load_account_panel, load_outlet_registry


REQUIRED_TOPICS = {"climate_change", "cost_of_living", "clean_transport", "electric_vehicles"}


def audit_configuration(config_dir: str | Path) -> dict[str, Any]:
    config_path = Path(config_dir)
    topics = load_config(config_path / "topics.uk-pilot.yaml")
    political = load_political_config(config_path / "political_signals.uk-pilot.yaml")
    outlets = load_outlet_registry(config_path / "outlet_registry.yaml")
    accounts = load_account_panel(config_path / "account_panel.yaml")
    topic_ids = {item.id for item in topics.topics}
    warnings: list[str] = []
    errors: list[str] = []
    missing_topics = sorted(REQUIRED_TOPICS - topic_ids)
    if missing_topics:
        errors.append(f"missing required topics: {', '.join(missing_topics)}")
    phrase_statuses = [phrase.translation_status for item in topics.topics for phrase in item.ngram_phrases]
    if any(status != "validated" for status in phrase_statuses):
        warnings.append("topic phrases are draft/review definitions; native-speaker and precision/recall review is pending")
    if not any(phrase.language == "cy" for item in topics.topics for phrase in item.ngram_phrases):
        warnings.append("Welsh (cy) coverage is not configured and remains a documented language gap")
    if len({item.domain for item in outlets}) != len(outlets):
        errors.append("outlet domains must be unique")
    if len({item.did for item in accounts}) != len(accounts):
        errors.append("account DIDs must be unique")
    if any(item.review_status != "reviewed" for item in accounts):
        warnings.append("Bluesky panel contains seed accounts that need T&E review")
    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "topics": sorted(topic_ids),
        "political_signals": len(political.signals),
        "outlets": len(outlets),
        "accounts": len(accounts),
        "panel_reviewed_accounts": sum(item.review_status == "reviewed" for item in accounts),
    }


def audit_release(data: dict[str, Any]) -> dict[str, Any]:
    """Check cross-table release and denominator invariants."""
    release = data.get("release", {})
    release_id = release.get("release_id")
    errors: list[str] = []
    warnings: list[str] = []
    if not release_id:
        errors.append("release.release_id is required")
    denominator_by_date = {row.get("date"): row.get("captured_article_count") for row in data.get("news_denominators", [])}
    daily = data.get("daily_attention", [])
    keys = [(row.get("date"), row.get("source"), row.get("topic_id"), row.get("measure"), row.get("geography", "GB")) for row in daily]
    duplicates = len(keys) - len(set(keys))
    if duplicates:
        errors.append(f"{duplicates} duplicate daily attention keys")
    mismatched_news = [row for row in daily if row.get("source") == "gdelt_ngrams" and row.get("denominator") != denominator_by_date.get(row.get("date"))]
    if mismatched_news:
        errors.append(f"{len(mismatched_news)} GDELT rows do not align to the daily denominator")
    missing_release_ids = []
    for collection in ("daily_attention", "social_posts", "physical_observations", "events", "articles", "data_layers"):
        for row in data.get(collection, []):
            if row.get("release_id") != release_id:
                missing_release_ids.append(f"{collection}:{row.get('release_id')}")
    if missing_release_ids:
        errors.append(f"{len(missing_release_ids)} records do not carry the active release ID")
    if not data.get("physical_observations"):
        warnings.append("no MODIS physical observation is available")
    if not data.get("events"):
        warnings.append("no event records are available")
    counts = Counter(row.get("source") for row in daily)
    return {"status": "fail" if errors else "pass", "errors": errors, "warnings": warnings, "release_id": release_id, "daily_rows": len(daily), "daily_rows_by_source": dict(counts), "denominator_dates": len(denominator_by_date), "article_rows": len(data.get("articles", [])), "social_rows": len(data.get("social_posts", []))}
