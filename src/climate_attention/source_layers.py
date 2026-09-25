"""Source-layer registry, parsers and deterministic fixtures.

Live collectors can replace the fixture readers without changing serving tables:
each adapter must emit ``ObservationRecord`` plus a ``SourceSnapshot``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from .contracts import DataLayerDefinition, ObservationRecord, QualityStatus, SourceSnapshot


ROOT = Path(__file__).resolve().parents[2]
RELEASE_ID = "uk-atlas-fixture-2026-09-23"
RUN_ID = "layers-fixture-run-2026-09-23"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _dt(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


def _days(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def load_layer_registry(path: str | Path = ROOT / "config/source_layers.yaml", *, release_id: str = RELEASE_ID) -> list[DataLayerDefinition]:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [DataLayerDefinition.model_validate({**item, "release_id": release_id}) for item in document.get("layers", [])]


def parse_csv_observations(
    text: str,
    *,
    source: str,
    series_id: str,
    metric: str,
    unit: str,
    geography: str = "GB",
    geography_level: str = "country",
    run_id: str = RUN_ID,
    release_id: str = RELEASE_ID,
) -> list[ObservationRecord]:
    """Parse a simple date,value CSV while preserving blank values as missing."""
    rows: list[ObservationRecord] = []
    for row in csv.DictReader(io.StringIO(text)):
        raw_value = (row.get("value") or "").strip()
        value = float(raw_value) if raw_value else None
        rows.append(ObservationRecord(
            observation_id=f"{source}_{series_id}_{row['date']}", source=source, series_id=series_id,
            metric=metric, observed_at=date.fromisoformat(row["date"]), geography=geography,
            geography_level=geography_level, value=value, unit=unit,
            quality_status=QualityStatus.observed if value is not None else QualityStatus.missing,
            completeness=1.0 if value is not None else 0.0, collection_run_id=run_id,
            collected_at=_dt(date.fromisoformat(row["date"]), 13), release_id=release_id,
        ))
    return rows


def parse_json_observations(
    payload: list[dict[str, Any]],
    *,
    source: str,
    series_id: str,
    metric: str,
    unit: str,
    geography: str = "GB",
    geography_level: str = "country",
    run_id: str = RUN_ID,
    release_id: str = RELEASE_ID,
) -> list[ObservationRecord]:
    """Normalise public-feed JSON records with explicit missingness."""
    result: list[ObservationRecord] = []
    for item in payload:
        observed_at = date.fromisoformat(str(item["date"])[:10])
        raw = item.get("value")
        value = float(raw) if raw is not None else None
        result.append(ObservationRecord(
            observation_id=str(item.get("id") or f"{source}_{series_id}_{observed_at}"), source=source,
            series_id=series_id, metric=metric, observed_at=observed_at, geography=geography,
            geography_level=geography_level, value=value, unit=unit,
            quality_status=QualityStatus.observed if value is not None else QualityStatus.missing,
            completeness=item.get("completeness", 1.0 if value is not None else 0.0),
            revision_status=item.get("revision_status", "not_applicable"), collection_run_id=run_id,
            collected_at=_dt(observed_at, 13), release_id=release_id, metadata=item.get("metadata", {}),
        ))
    return result


def build_layer_fixture(start: date = date(2026, 8, 1), end: date = date(2026, 8, 30), *, release_id: str = RELEASE_ID, run_id: str = RUN_ID) -> dict[str, Any]:
    """Build source-separated records for every layer that can be prepared locally."""
    observations: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []

    def add(source: str, series: str, metric: str, unit: str, day: date, value: float | None,
            *, geography: str = "GB", geography_level: str = "country", status: QualityStatus | None = None,
            completeness: float | None = 1.0, revision: str = "initial", metadata: dict[str, Any] | None = None):
        observations.append(ObservationRecord(
            observation_id=f"{source}_{series}_{day.isoformat()}", source=source, series_id=series,
            metric=metric, observed_at=day, geography=geography, geography_level=geography_level,
            value=value, unit=unit, quality_status=status or (QualityStatus.observed if value is not None else QualityStatus.missing),
            completeness=completeness, revision_status=revision, collection_run_id=run_id,
            collected_at=_dt(day, 14), release_id=release_id, metadata=metadata or {},
        ).model_dump(mode="json"))

    for index, day in enumerate(_days(start, end)):
        add("desnz_fuel_prices", "uk_petrol", "petrol_pump_price", "pence_per_litre", day, round(143.2 + (index % 7) * 0.35, 2), metadata={"fuel": "unleaded_95", "market": "UK_average"})
        add("desnz_fuel_prices", "uk_diesel", "diesel_pump_price", "pence_per_litre", day, round(151.8 + (index % 6) * 0.42, 2), metadata={"fuel": "road_diesel", "market": "UK_average"})
        add("haduk_grid_weather", "tas_anomaly", "temperature_anomaly", "degrees_celsius", day, round(1.1 + ((index % 9) - 4) * 0.12, 2), metadata={"grid": "5km", "baseline": "1961-1990"})
        add("haduk_grid_weather", "precipitation", "precipitation_total", "millimetres", day, round(2.0 + (index % 5) * 1.4, 1), metadata={"grid": "5km"})
        add("environment_agency_alerts", "flood_alerts", "flood_alert_count", "alerts", day, float((index * 3) % 4), geography_level="region", metadata={"feed": "fixture_public_alerts"})
        add("rail_disruption", "uk_delay_minutes", "train_delay_minutes", "minutes", day, float((index * 11) % 190), metadata={"scope": "fixture_network_total"})
        add("rail_disruption", "uk_cancellations", "train_cancellation_count", "cancellations", day, float((index * 2) % 12), metadata={"scope": "fixture_network_total"})
        add("brent_oil", "brent_spot", "brent_price", "usd_per_barrel", day, round(81.0 + (index % 8) * 0.8, 2), geography="market", geography_level="market", metadata={"currency": "USD"})
        add("ftse100", "ftse100_close", "ftse100_close", "index_points", day, round(8160 + (index * 13) % 240, 1), geography="market", geography_level="market", metadata={"market": "LSE"})
        add("local_disruption", "fixture_local_incidents", "incident_count", "incidents", day, float((index + 1) % 5), geography="GB-LA", geography_level="local_authority", status=QualityStatus.partial, completeness=0.25, metadata={"coverage": "fixture placeholder; local feed not selected"})
        add("firms_hotspots", "uk_active_fire", "active_fire_hotspot_count", "hotspots", day, float(index % 4), metadata={"confidence": "nominal"})
    # Monthly/official access layers retain a visible missing state in the same archive.
    add("ons_cost_pressures", "cpi_all_items", "consumer_price_index", "index_2015_100", start, 137.4, revision="initial", metadata={"period": "2026-08", "series_status": "fixture"})
    add("ons_cost_pressures", "food_cpi", "food_price_change", "percent_change_yoy", start, 3.7, revision="initial", metadata={"period": "2026-08"})
    add("modis_burned_area", "uk_burned_area", "burned_area", "hectares", start, 128.0, metadata={"product": "MCD64A1.061", "valid_area_fraction": 0.88})
    add("google_trends_official", "climate_change", "search_interest", "index_0_100", start, None, status=QualityStatus.unsupported, completeness=0.0, metadata={"reason": "official API access pending"})
    add("polling_opinion", "climate_change_concern", "climate_concern_share", "percent", start, None, status=QualityStatus.unsupported, completeness=0.0, metadata={"reason": "poll source and publication rights pending", "candidate_sources": ["British Election Study", "YouGov", "Ipsos", "Greenpeace"]})
    add("local_disruption", "approved_local_feed", "incident_count", "incidents", start, None, status=QualityStatus.unsupported, completeness=0.0, geography="GB", metadata={"reason": "local feed inventory pending"})

    for definition in load_layer_registry(release_id=release_id):
        layer_rows = [row for row in observations if row["source"] == definition.layer_id]
        observed = [row for row in layer_rows if row["value"] is not None]
        statuses = {row["quality_status"] for row in layer_rows}
        snapshot_status = "fixture" if observed else "access_pending"
        if QualityStatus.unsupported.value in statuses and not observed:
            snapshot_status = "access_pending"
        snapshots.append(SourceSnapshot(
            source=definition.layer_id, snapshot_id=f"{definition.layer_id}-fixture-v1", status=snapshot_status,
            observed_start=min((row["observed_at"] for row in layer_rows), default=None),
            observed_end=max((row["observed_at"] for row in layer_rows), default=None), retrieved_at=_dt(end, 16),
            endpoint=definition.source_url, request_count=0, rate_limit_note="Fixture; no provider request made.",
            completeness=round(len(observed) / len(layer_rows), 3) if layer_rows else 0.0,
            notes=definition.access_requirement, release_id=release_id,
        ).model_dump(mode="json"))
    return {
        "schema_version": 1, "release_id": release_id, "run_id": run_id,
        "observations": observations, "source_snapshots": snapshots,
        "layer_definitions": [item.model_dump(mode="json") for item in load_layer_registry(release_id=release_id)],
    }


def layer_quality_report(data: dict[str, Any]) -> dict[str, Any]:
    from .sources.units import unit_quality_report

    rows = data.get("observations", [])
    keys = [(row.get("source"), row.get("series_id"), row.get("observed_at"), row.get("geography")) for row in rows]
    duplicates = len(keys) - len(set(keys))
    sources = {row.get("source") for row in rows}
    snapshot_sources = {row.get("source") for row in data.get("source_snapshots", [])}
    missing_snapshots = sorted(sources - snapshot_sources)
    unit_report = unit_quality_report(rows)
    return {
        "status": "fail" if duplicates or missing_snapshots or unit_report["status"] == "fail" else "pass",
        "observation_rows": len(rows), "sources": sorted(sources), "duplicate_keys": duplicates,
        "missing_snapshots": missing_snapshots,
        "unit_errors": unit_report["errors"],
        "missing_rows": sum(row.get("quality_status") in {"missing", "unsupported", "outage"} for row in rows),
        "partial_rows": sum(row.get("quality_status") == "partial" for row in rows),
    }


def write_layer_parquet(data: dict[str, Any], path: str | Path) -> Path:
    """Write an atomic, versioned observation table for the research archive."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    table = pa.Table.from_pylist(data.get("observations", []))
    pq.write_table(table, temporary, compression="zstd")
    temporary.replace(destination)
    return destination
