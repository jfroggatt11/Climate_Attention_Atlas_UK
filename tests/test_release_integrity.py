from copy import deepcopy

from climate_attention.pipeline import build_fixture, release_content_hash
from climate_attention.validation import audit_release


def test_fixture_is_byte_reproducible_and_has_release_content_hash():
    first = build_fixture()
    second = build_fixture()
    assert first == second
    assert first["release"]["created_at"] == "2026-08-31T12:00:00Z"
    assert first["release"]["content_hash"] == release_content_hash(first)
    assert len(first["release"]["configuration_files"]) == 7


def test_release_audit_rejects_incoherent_gdelt_arithmetic_and_social_denominator():
    fixture = build_fixture()
    assert audit_release(fixture)["status"] == "pass"

    tampered_news = deepcopy(fixture)
    tampered_news["daily_attention"][0]["value"] = 0.0
    assert audit_release(tampered_news)["status"] == "fail"

    tampered_social = deepcopy(fixture)
    social_row = next(row for row in tampered_social["daily_attention"] if row["source"] == "bluesky")
    social_row["denominator"] += 1
    assert audit_release(tampered_social)["status"] == "fail"
