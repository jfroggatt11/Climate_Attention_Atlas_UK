"""Pre-publication audits that can run before provider access is granted."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
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
    denominator_rows = data.get("news_denominators", [])
    denominator_by_date = {row.get("date"): row for row in denominator_rows}
    if len(denominator_by_date) != len(denominator_rows):
        errors.append("GDELT daily denominator dates must be unique")
    for row in denominator_rows:
        count = row.get("captured_article_count")
        manifest = row.get("captured_url_manifest") or {}
        if manifest.get("count") != count or manifest.get("algorithm") != "sha256-truncated-12" or not manifest.get("seed"):
            errors.append(f"{row.get('date')} captured URL universe does not reconcile to its denominator")
        hashes = [hashlib.sha256(f"{manifest.get('seed')}:{item}".encode()).hexdigest()[:12] for item in range(count or 0)]
        expected_universe_hash = hashlib.sha256(",".join(hashes).encode("utf-8")).hexdigest()
        if row.get("capture_universe_hash") != expected_universe_hash:
            errors.append(f"{row.get('date')} captured URL universe hash is invalid")
    daily = data.get("daily_attention", [])
    keys = [(row.get("date"), row.get("source"), row.get("topic_id"), row.get("measure"), row.get("geography", "GB")) for row in daily]
    duplicates = len(keys) - len(set(keys))
    if duplicates:
        errors.append(f"{duplicates} duplicate daily attention keys")
    mismatched_news = []
    for row in daily:
        if row.get("source") != "gdelt_ngrams":
            continue
        denominator = denominator_by_date.get(row.get("date"))
        if not denominator or row.get("denominator") != denominator.get("captured_article_count"):
            mismatched_news.append(row)
            continue
        if denominator.get("captured_article_count", 0) <= 0:
            errors.append(f"{row.get('date')} GDELT denominator must be positive for a share")
            continue
        matched = row.get("metadata", {}).get("matched_url_range") or {}
        numerator = row.get("metadata", {}).get("raw_article_count")
        if matched.get("count") != numerator or matched.get("start", -1) < 0 or matched.get("start", 0) + matched.get("count", 0) > denominator.get("captured_article_count", 0):
            errors.append(f"{row.get('date')} {row.get('topic_id')} GDELT numerator is not drawn from the captured URL universe")
        if row.get("metadata", {}).get("capture_universe_hash") != denominator.get("capture_universe_hash"):
            errors.append(f"{row.get('date')} {row.get('topic_id')} GDELT universe hash does not match its denominator")
        expected_share = round(float(numerator) / float(denominator["captured_article_count"]), 5)
        if row.get("value") != expected_share:
            errors.append(f"{row.get('date')} {row.get('topic_id')} GDELT share is not numerator divided by denominator")
    if mismatched_news:
        errors.append(f"{len(mismatched_news)} GDELT rows do not align to the daily denominator")

    posts_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in data.get("social_posts", []):
        posts_by_date[str(post.get("posted_at", ""))[:10]].append(post)
    for row in daily:
        if row.get("source") != "bluesky":
            continue
        day_posts = posts_by_date.get(row.get("date"), [])
        denominator = row.get("denominator")
        if denominator != len(day_posts):
            errors.append(f"{row.get('date')} Bluesky denominator is not the observed post count")
        if not isinstance(denominator, (int, float)) or denominator <= 0:
            errors.append(f"{row.get('date')} Bluesky denominator must be positive for a share")
            continue
        observed_ids = row.get("metadata", {}).get("observed_panel_post_ids") or []
        if set(observed_ids) != {post.get("post_id") for post in day_posts}:
            errors.append(f"{row.get('date')} Bluesky denominator panel IDs do not match observed posts")
        numerator = row.get("metadata", {}).get("raw_post_count")
        expected = sum(row.get("topic_id") in (post.get("topic_ids") or []) for post in day_posts)
        if numerator != expected or row.get("value") != round(numerator / denominator, 5):
            errors.append(f"{row.get('date')} {row.get('topic_id')} Bluesky share is not numerator divided by observed denominator")
    missing_release_ids = []
    for collection in ("daily_attention", "news_denominators", "social_posts", "physical_observations", "events", "articles", "data_layers", "source_snapshots", "layer_definitions"):
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
