"""Source-specific unit and metric checks."""

from __future__ import annotations

from typing import Any


EXPECTED_UNITS: dict[str, set[str]] = {
    "desnz_fuel_prices": {"pence_per_litre"},
    "ons_cost_pressures": {"index_2015_100", "percent_change_yoy"},
    "haduk_grid_weather": {"degrees_celsius", "millimetres"},
    "environment_agency_alerts": {"alerts"},
    "rail_disruption": {"minutes", "cancellations"},
    "brent_oil": {"usd_per_barrel"},
    "ftse100": {"index_points"},
    "google_trends_official": {"index_0_100"},
    "polling_opinion": {"percent", "sample_size"},
    "local_disruption": {"incidents"},
    "firms_hotspots": {"hotspots"},
    "modis_burned_area": {"hectares"},
}


def validate_layer_units(row: dict[str, Any]) -> list[str]:
    expected = EXPECTED_UNITS.get(row.get("source"), set())
    if not expected:
        return [f"unregistered source: {row.get('source')}"]
    if row.get("unit") not in expected:
        return [f"{row.get('source')} expects one of {sorted(expected)}, got {row.get('unit')!r}"]
    if row.get("value") is not None and row.get("source") == "google_trends_official" and not 0 <= row["value"] <= 100:
        return ["Google Trends index must be between 0 and 100"]
    return []


def unit_quality_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [error for row in rows for error in validate_layer_units(row)]
    return {"status": "fail" if errors else "pass", "errors": errors, "checked_rows": len(rows)}
