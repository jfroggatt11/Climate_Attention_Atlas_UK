from datetime import datetime, timezone

from climate_attention.contracts import AccountPanelEntry, SocialPost
from climate_attention.sources.bluesky import daily_panel_denominators, deduplicate_posts


def post(uri: str, hour: int, updated: bool = False) -> SocialPost:
    return SocialPost(
        post_id=f"id-{hour}-{updated}", account_did="did:plc:abcde", handle="panel.example",
        post_uri=uri, posted_at=datetime(2026, 8, 1, hour, tzinfo=timezone.utc),
        topic_ids=["climate_change"], updated=updated, collection_run_id="run", release_id="release",
    )


def test_post_deduplication_keeps_latest_uri():
    result = deduplicate_posts([post("at://same", 8), post("at://same", 9, True), post("at://other", 10)])
    assert [item.post_uri for item in result] == ["at://same", "at://other"]
    assert result[0].updated is True


def test_panel_denominator_counts_observed_posts():
    assert daily_panel_denominators([post("at://a", 8), post("at://b", 9)], panel_size=1) == {datetime(2026, 8, 1, tzinfo=timezone.utc).date(): 2}
