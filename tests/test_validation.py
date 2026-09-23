import json
from pathlib import Path

from climate_attention.validation import audit_configuration, audit_release


def test_configuration_audit_reports_seed_panel_and_draft_topics():
    result = audit_configuration(Path(__file__).parents[1] / "config")
    assert result["status"] == "pass"
    assert set(result["topics"]) == {"climate_change", "cost_of_living", "clean_transport", "electric_vehicles"}
    assert result["panel_reviewed_accounts"] == 0
    assert result["warnings"]


def test_fixture_release_audit_checks_cross_table_ids():
    fixture = json.loads((Path(__file__).parents[1] / "data/fixtures/vertical-slice.json").read_text())
    result = audit_release(fixture)
    assert result["status"] == "pass"
    assert result["denominator_dates"] == 30
    assert result["daily_rows_by_source"]["gdelt_ngrams"] == 120
