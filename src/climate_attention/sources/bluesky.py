"""Narrow Bluesky monitored-panel adapter helpers.

The first release uses public AppView reads. The functions here keep cursors,
deletes and updates explicit so a later Jetstream collector can use the same
normalised records without changing the aggregate contract.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Iterable

from ..contracts import AccountPanelEntry, SocialPost


def normalise_post(raw: dict[str, Any], *, panel: dict[str, AccountPanelEntry], run_id: str, release_id: str) -> SocialPost | None:
    author = raw.get("author") or {}
    did = str(author.get("did") or raw.get("account_did") or "")
    account = panel.get(did)
    if account is None or raw.get("record_type") == "delete":
        return None
    value = raw.get("record", raw)
    posted = value.get("createdAt") or value.get("posted_at")
    if not posted:
        return None
    if posted.endswith("Z"):
        posted = posted[:-1] + "+00:00"
    return SocialPost(
        post_id=str(raw.get("id") or raw.get("post_id") or raw.get("uri")),
        account_did=did,
        handle=account.handle,
        post_uri=str(raw.get("uri") or raw.get("post_uri")),
        posted_at=datetime.fromisoformat(posted).astimezone(timezone.utc),
        text=value.get("text"),
        topic_ids=list(raw.get("topic_ids", [])),
        deleted=False,
        updated=bool(raw.get("updated", False)),
        cursor=raw.get("cursor"),
        source="bluesky_jetstream" if raw.get("source") == "jetstream" else "bluesky_appview",
        collection_run_id=run_id,
        release_id=release_id,
    )


def deduplicate_posts(posts: Iterable[SocialPost]) -> list[SocialPost]:
    """Keep the latest update for each stable post URI."""
    latest: dict[str, SocialPost] = {}
    for post in posts:
        current = latest.get(post.post_uri)
        if current is None or post.posted_at >= current.posted_at:
            latest[post.post_uri] = post
    return sorted(latest.values(), key=lambda post: post.posted_at)


def daily_panel_denominators(posts: Iterable[SocialPost], panel_size: int) -> dict[date, int]:
    """Return observed panel-post totals; callers must retain incomplete days."""
    result: Counter[date] = Counter(post.posted_at.date() for post in posts if not post.deleted)
    return dict(result)
