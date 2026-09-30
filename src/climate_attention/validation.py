"""Pre-publication audits that can run before provider access is granted."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import random
import math
from pathlib import Path
from typing import Any

from .config import load_config, load_country_config, load_political_config
from .panel import load_account_panel, load_outlet_registry
from .registries import load_event_registry


REQUIRED_TOPICS = {"climate_change", "fuel_prices", "clean_transport", "electric_vehicles", "extreme_weather"}


def build_article_validation_sample(
    articles: list[dict[str, Any]],
    *,
    tag_ids: list[str],
    sample_size: int = 1000,
    seed: int = 20260929,
) -> list[dict[str, Any]]:
    """Create a reproducible review template that includes unmatched articles.

    Rows are sampled from the full captured inventory, then enriched with rare
    tag candidates so matched-only sampling cannot masquerade as recall review.
    Human label columns are intentionally null until adjudication.
    """
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    by_id = {str(row.get("article_id")): row for row in articles if row.get("article_id")}
    if not by_id:
        return []
    tag_rows = {tag_id: [] for tag_id in tag_ids}
    for row in articles:
        for tag_id in row.get("candidate_tag_ids", []):
            if tag_id in tag_rows:
                tag_rows[tag_id].append(row)
    selected: dict[str, dict[str, Any]] = {}
    for tag_id, rows in tag_rows.items():
        if rows:
            candidate = min(rows, key=lambda row: hashlib.sha256(f"{seed}:{tag_id}:{row['article_id']}".encode()).hexdigest())
            selected[str(candidate["article_id"])] = candidate
    remaining = [row for row in by_id.values() if str(row["article_id"]) not in selected]
    rng = random.Random(seed)
    rng.shuffle(remaining)
    for row in remaining[: max(0, sample_size - len(selected))]:
        selected[str(row["article_id"])] = row
    output: list[dict[str, Any]] = []
    for article_id, row in sorted(selected.items()):
        output.append({
            "article_id": article_id,
            "url": row.get("canonical_url") or row.get("url"),
            "outlet_id": row.get("outlet_id"),
            "language": row.get("language"),
            "candidate_tag_ids": list(row.get("candidate_tag_ids", [])),
            "labels": {tag_id: None for tag_id in tag_ids},
            "substantive_labels": {tag_id: None for tag_id in tag_ids},
            "event_identity": None,
            "political_entities": None,
            "location_roles": None,
            "review_status": "unreviewed",
        })
    return output


def score_article_validation(
    rows: list[dict[str, Any]], *, tag_ids: list[str], label_key: str = "labels",
) -> dict[str, Any]:
    """Score reviewed mention labels against deterministic candidate positives.

    Unknown/unreviewed labels are excluded.  The returned Wilson intervals make
    small rare-tag samples visible instead of presenting unstable percentages.
    """
    report: dict[str, Any] = {}
    for tag_id in tag_ids:
        tp = fp = fn = reviewed = 0
        for row in rows:
            label = (row.get(label_key) or {}).get(tag_id)
            if label not in {True, False, "yes", "no", "positive", "negative"}:
                continue
            reviewed += 1
            actual = label is True or label in {"yes", "positive"}
            predicted = tag_id in set(row.get("candidate_tag_ids", []))
            tp += int(actual and predicted)
            fp += int(not actual and predicted)
            fn += int(actual and not predicted)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        report[tag_id] = {
            "reviewed": reviewed, "true_positive": tp, "false_positive": fp,
            "false_negative": fn, "precision": precision, "recall": recall,
            "precision_wilson_95": _wilson(tp, tp + fp),
            "recall_wilson_95": _wilson(tp, tp + fn),
        }
    return report


def _wilson(successes: int, trials: int, z: float = 1.96) -> list[float] | None:
    if trials == 0:
        return None
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denominator
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def audit_configuration(config_dir: str | Path) -> dict[str, Any]:
    config_path = Path(config_dir)
    topics = load_config(config_path / "topics.uk-pilot.yaml")
    political = load_political_config(config_path / "political_signals.uk-pilot.yaml")
    countries = load_country_config(config_path / "countries.uk-pilot.yaml")
    outlets = load_outlet_registry(config_path / "outlet_registry.yaml")
    accounts = load_account_panel(config_path / "account_panel.yaml")
    event_registry_version, events = load_event_registry(config_path / "events.uk-pilot.yaml") if (config_path / "events.uk-pilot.yaml").exists() else ("events-v1", [])
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
        # ``topics`` preserves the original four-topic audit field for
        # downstream consumers; the expanded catalogue is available explicitly
        # so adding a selectable tag does not break older release tooling.
        "topics": sorted(topic_ids & REQUIRED_TOPICS),
        "selectable_topics": sorted(topic_ids),
        "political_signals": len(political.signals),
        "outlets": len(outlets),
        "accounts": len(accounts),
        "countries": len(countries.countries),
        "panel_reviewed_accounts": sum(item.review_status == "reviewed" for item in accounts),
        "event_registry_version": event_registry_version,
        "tracked_events": len(events),
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
