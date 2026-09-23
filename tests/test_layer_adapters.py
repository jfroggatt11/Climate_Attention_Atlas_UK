from datetime import date

from climate_attention.source_layers import build_layer_fixture, layer_quality_report
from climate_attention.sources.layers import parse_fixture_payload, request_plan
from climate_attention.sources.units import unit_quality_report


def test_request_plan_is_explicit_and_makes_no_request():
    plan = request_plan("desnz_fuel_prices", date(2026, 8, 1), date(2026, 8, 7))
    assert plan["request_made"] is False
    assert plan["auth_required"] is False


def test_csv_fixture_adapter_emits_canonical_observations():
    rows = parse_fixture_payload(
        "desnz_fuel_prices", "date,value\n2026-08-01,144.2\n",
        series_id="uk_petrol", metric="petrol_pump_price", unit="pence_per_litre",
    )
    assert rows[0].source == "desnz_fuel_prices"
    assert rows[0].unit == "pence_per_litre"


def test_layer_fixture_units_are_validated():
    data = build_layer_fixture(date(2026, 8, 1), date(2026, 8, 2))
    assert layer_quality_report(data)["status"] == "pass"
    assert unit_quality_report(data["observations"])["status"] == "pass"
