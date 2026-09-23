from datetime import date

from climate_attention.contracts import QualityStatus
from climate_attention.source_layers import build_layer_fixture, layer_quality_report, parse_csv_observations


def test_csv_parser_preserves_blank_as_missing():
    rows = parse_csv_observations(
        "date,value\n2026-08-01,12.5\n2026-08-02,\n",
        source="test", series_id="series", metric="metric", unit="units",
    )
    assert rows[0].value == 12.5
    assert rows[1].value is None
    assert rows[1].quality_status == QualityStatus.missing


def test_layer_fixture_covers_planned_sources_and_keeps_pending_rows_explicit():
    data = build_layer_fixture(date(2026, 8, 1), date(2026, 8, 3))
    report = layer_quality_report(data)
    assert report["status"] == "pass"
    sources = set(report["sources"])
    assert {"desnz_fuel_prices", "ons_cost_pressures", "haduk_grid_weather", "rail_disruption", "brent_oil", "ftse100", "google_trends_official"} <= sources
    trends = [row for row in data["observations"] if row["source"] == "google_trends_official"]
    assert trends[0]["value"] is None
    assert trends[0]["quality_status"] == "unsupported"
