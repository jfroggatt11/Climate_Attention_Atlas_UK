"""Provider adapter boundaries for the expanded UK source layer registry.

These adapters deliberately separate request planning from parsing. A later live
collector can supply an approved response payload without changing the normalized
``ObservationRecord`` contract or its quality metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from ..source_layers import parse_csv_observations, parse_json_observations


@dataclass(frozen=True)
class LayerAdapter:
    source_id: str
    endpoint: str | None
    cadence: str
    auth_required: bool
    parser_kind: str
    access_note: str

    def request_plan(self, start: date, end: date) -> dict[str, Any]:
        return {
            "source": self.source_id,
            "endpoint": self.endpoint,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "cadence": self.cadence,
            "auth_required": self.auth_required,
            "parser": self.parser_kind,
            "request_made": False,
            "access_note": self.access_note,
        }


ADAPTERS: tuple[LayerAdapter, ...] = (
    LayerAdapter("desnz_fuel_prices", "https://www.gov.uk/government/collections/road-fuel-prices", "weekly", False, "csv_or_xlsx", "Confirm revision and licence terms."),
    LayerAdapter("ons_cost_pressures", "https://www.ons.gov.uk/economy/inflationandpriceindices", "monthly", False, "json_or_csv", "Pin ONS series identifiers and revision status."),
    LayerAdapter("haduk_grid_weather", "https://www.metoffice.gov.uk/research/climate/maps-and-data", "monthly", False, "netcdf_or_csv", "Confirm HadUK-Grid access and licence."),
    LayerAdapter("environment_agency_alerts", "https://environment.data.gov.uk/", "event_driven", False, "geojson_or_json", "Confirm alert geography and update semantics."),
    LayerAdapter("rail_disruption", "https://www.orr.gov.uk/", "daily", True, "csv_or_json", "Operator or ORR data agreement required."),
    LayerAdapter("brent_oil", "https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm", "daily", False, "csv_or_json", "Confirm source terms and delayed-data policy."),
    LayerAdapter("ftse100", "https://www.londonstockexchange.com/", "daily", True, "csv_or_json", "Confirm market-data licensing before publication."),
    LayerAdapter("google_trends_official", "https://developers.google.com/", "daily", True, "json", "Official API access and publication terms pending."),
    LayerAdapter("polling_opinion", None, "on_demand", True, "json_or_csv", "Approve poll question wording, fieldwork metadata, weighting and publication rights before ingestion."),
    LayerAdapter("local_disruption", None, "event_driven", True, "json_or_geojson", "Approve local feed inventory and geography mapping."),
    LayerAdapter("firms_hotspots", "https://firms.modaps.eosdis.nasa.gov/", "daily", True, "csv", "T&E-owned FIRMS key required for durable refresh."),
    LayerAdapter("modis_burned_area", "https://lpdaac.usgs.gov/products/mcd64a1v061/", "monthly", True, "raster_or_zonal_csv", "Earthdata access and processing resources required."),
)


ADAPTER_BY_SOURCE = {adapter.source_id: adapter for adapter in ADAPTERS}


def request_plan(source: str, start: date, end: date) -> dict[str, Any]:
    try:
        adapter = ADAPTER_BY_SOURCE[source]
    except KeyError as exc:
        raise ValueError(f"unknown source layer: {source}") from exc
    return adapter.request_plan(start, end)


def parse_fixture_payload(source: str, payload: str | list[dict[str, Any]], **kwargs: Any):
    """Use the declared parser shape for a source without making a request."""
    adapter = ADAPTER_BY_SOURCE[source]
    if adapter.parser_kind in {"csv", "csv_or_xlsx", "json_or_csv", "netcdf_or_csv"} and isinstance(payload, str):
        return parse_csv_observations(payload, source=source, **kwargs)
    if isinstance(payload, list):
        return parse_json_observations(payload, source=source, **kwargs)
    raise ValueError(f"payload shape does not match parser for {source}")
