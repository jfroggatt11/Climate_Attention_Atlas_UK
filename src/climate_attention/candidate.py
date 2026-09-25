"""Assemble a reviewable physical-context candidate from live source bundles."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .config import release_config_hash, release_config_hashes
from .contracts import DatasetRelease, EventRecord, ObservationRecord, PhysicalObservation, SourceSnapshot
from .pipeline import CONFIG, release_content_hash, write_json
from .source_layers import layer_quality_report
from .validation import audit_release


REQUIRED = ("haduk_grid_weather", "modis_mod13c2", "gdacs", "firms")
OPTIONAL = (
    "environment_agency_alerts", "modis_burned_area", "desnz_fuel_prices",
    "ons_cost_pressures", "brent_oil", "market_prices",
)


def _load_bundle(root: Path, source: str) -> tuple[dict[str, Any], str]:
    path = root / source / "bundle.json"
    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload.get("source") != source or not isinstance(payload.get("records"), list):
        raise ValueError(f"invalid {source} bundle: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def build_candidate(root: Path, *, start: date, end: date) -> dict[str, Any]:
    """Promote only real, source-linked rows; keep missing attention empty."""
    if end < start:
        raise ValueError("candidate end precedes start")
    bundles = {source: _load_bundle(root, source) for source in REQUIRED}
    for source in OPTIONAL:
        if (root / source / "bundle.json").is_file():
            bundles[source] = _load_bundle(root, source)
    created_at = datetime.now(timezone.utc)
    release_id = f"uk-atlas-candidate-{start.isoformat()}-{end.isoformat()}"
    snapshots: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    for source, (bundle, digest) in bundles.items():
        original = bundle["source_snapshot"]
        snapshot = SourceSnapshot.model_validate({
            **{key: value for key, value in original.items() if key in SourceSnapshot.model_fields},
            "release_id": release_id,
            "snapshot_id": f"{source}-{digest[:12]}",
        })
        snapshots.append(snapshot.model_dump(mode="json"))
        source_hashes[source] = digest

    weather = []
    for row in bundles["haduk_grid_weather"][0]["records"]:
        observed = date.fromisoformat(row["observed_at"])
        if start <= observed <= end:
            weather.append(ObservationRecord.model_validate({
                **row,
                "release_id": release_id,
                "collected_at": bundles["haduk_grid_weather"][0]["source_snapshot"]["retrieved_at"],
                "revision_status": "final",
                "metadata": {**row.get("metadata", {}), "source_bundle_sha256": source_hashes["haduk_grid_weather"]},
            }).model_dump(mode="json"))

    physical = []
    for row in bundles["modis_mod13c2"][0]["records"]:
        observed = date.fromisoformat(row["date"])
        if not (start <= observed <= end) or row.get("country_iso3") != "GBR":
            continue
        valid, total = row.get("valid_pixel_count"), row.get("total_pixel_count")
        physical.append(PhysicalObservation(
            observation_id=row["record_id"], source="modis_mod13c2", metric="ndvi",
            observed_at=observed, geography="GB", value=row["value"], unit="index",
            baseline_start_year=row.get("baseline_start_year"),
            baseline_end_year=row.get("baseline_end_year"),
            valid_area_fraction=(valid / total if valid is not None and total else None),
            release_id=release_id,
            metadata={"product": row["product"], "granule_id": row.get("metadata", {}).get("granule_id"),
                      "valid_pixel_count": valid, "total_pixel_count": total,
                      "aggregation": row.get("metadata", {}).get("aggregation"),
                      "source_bundle_sha256": source_hashes["modis_mod13c2"],
                      "anomaly": row.get("anomaly"),
                      "standardized_anomaly": row.get("standardized_anomaly"),
                      "baseline_start_year": row.get("baseline_start_year"),
                      "baseline_end_year": row.get("baseline_end_year"),
                      "note": "Raw NDVI index; greenness anomaly is retained separately when the UK calendar-month baseline is available."},
        ).model_dump(mode="json"))
        if row.get("anomaly") is not None:
            physical.append(PhysicalObservation(
                observation_id=f"{row['record_id']}:anomaly", source="modis_mod13c2", metric="ndvi_anomaly",
                observed_at=observed, geography="GB", value=float(row["anomaly"]), unit="index_anomaly",
                baseline_start_year=row.get("baseline_start_year"),
                baseline_end_year=row.get("baseline_end_year"),
                valid_area_fraction=(valid / total if valid is not None and total else None),
                release_id=release_id,
                metadata={"product": row["product"], "granule_id": row.get("metadata", {}).get("granule_id"),
                          "standardized_anomaly": row.get("standardized_anomaly"),
                          "source_bundle_sha256": source_hashes["modis_mod13c2"],
                          "baseline_start_year": row.get("baseline_start_year"),
                          "baseline_end_year": row.get("baseline_end_year"),
                          "note": "NDVI anomaly relative to the matching calendar month in the 2001–2020 UK baseline."},
            ).model_dump(mode="json"))
    for row in bundles["firms"][0]["records"]:
        observed = date.fromisoformat(row["date"])
        if not (start <= observed <= end) or row.get("country_iso3") != "GBR":
            continue
        physical.append(PhysicalObservation(
            observation_id=row["record_id"], source="firms", metric="hotspot_count",
            observed_at=observed, geography="GB", value=row["observation_count"], unit="detections",
            release_id=release_id,
            metadata={"product": row.get("metadata", {}).get("provider_product"),
                      "request_complete": row.get("request_complete"),
                      "boundary_supported": row.get("boundary_supported"),
                      "source_bundle_sha256": source_hashes["firms"],
                      "note": "VIIRS detections, not distinct wildfires or burned area."},
        ).model_dump(mode="json"))

    # Economic, alert and additional climate bundles use the common observation
    # shape. Promote them into the same source-specific physical table without
    # flattening their units or cadences into the attention series.
    for source in OPTIONAL:
        if source not in bundles:
            continue
        for row in bundles[source][0]["records"]:
            observed_text = row.get("date") or row.get("observed_at")
            if not observed_text:
                continue
            observed = date.fromisoformat(str(observed_text)[:10])
            if not (start <= observed <= end) or row.get("value") is None:
                continue
            physical.append(PhysicalObservation(
                observation_id=row.get("record_id") or f"{source}:{row.get('series_id', row.get('metric'))}:{observed}",
                source=source,
                metric=row.get("metric", row.get("series_id", "value")),
                observed_at=observed,
                geography=row.get("geography", "GB"),
                value=float(row["value"]),
                unit=row.get("unit", "unknown"),
                release_id=release_id,
                metadata={**row.get("metadata", {}), "series_id": row.get("series_id"), "source_bundle_sha256": source_hashes[source]},
            ).model_dump(mode="json"))

    events = []
    for row in bundles["gdacs"][0]["records"]:
        if "GBR" not in row.get("country_iso3s", []):
            continue
        began = date.fromisoformat(row["start_at"][:10])
        finished = date.fromisoformat((row.get("end_at") or row["start_at"])[:10])
        if finished < start or began > end:
            continue
        events.append(EventRecord(
            event_id=row["record_id"], source="gdacs", event_type=row["hazard_type"],
            name=row["name"], start_at=row["start_at"], end_at=row.get("end_at"),
            geography_ids=["GB"], country_codes=row["country_iso3s"],
            alert_level=row.get("alert_level"), source_url=row.get("source_url"),
            geometry=row.get("geometry"), release_id=release_id,
        ).model_dump(mode="json"))

    definitions = [
        {"layer_id": "haduk_grid_weather", "label": "HadUK-Grid UK weather", "provider": "Met Office HadUK-Grid", "cadence": "monthly", "geography": "GB", "units": ["degrees_celsius"], "status": "adapter_ready", "source_url": "https://catalogue.ceda.ac.uk/uuid/ca4c331d666f4395b1346db9070094ab/", "access_requirement": "CEDA archive token", "independence_note": "Country area-average observed temperature; annual archive release.", "release_id": release_id},
        {"layer_id": "modis_mod13c2", "label": "MODIS greenness (NDVI)", "provider": "NASA Earthdata", "cadence": "monthly", "geography": "GB", "units": ["index", "index_anomaly"], "status": "adapter_ready", "source_url": "https://lpdaac.usgs.gov/products/mod13c2v061/", "access_requirement": "Earthdata Login", "independence_note": "One monthly satellite greenness source with two measures: raw NDVI and difference from the UK calendar-month 2001–2020 baseline.", "release_id": release_id},
        {"layer_id": "firms", "label": "NASA FIRMS active-fire detections", "provider": "NASA FIRMS", "cadence": "daily", "geography": "GB", "units": ["detections"], "status": "adapter_ready", "source_url": "https://firms.modaps.eosdis.nasa.gov/", "access_requirement": "FIRMS MAP_KEY", "independence_note": "Satellite detections are not named fires or burned area.", "release_id": release_id},
        {"layer_id": "gdacs", "label": "GDACS major events", "provider": "GDACS", "cadence": "event_driven", "geography": "GB", "units": ["events"], "status": "adapter_ready", "source_url": "https://www.gdacs.org/", "access_requirement": "Public API", "independence_note": "Named event catalogue remains separate from attention and hotspot counts.", "release_id": release_id},
    ]
    optional_definitions = {
        "environment_agency_alerts": ("Environment Agency flood alerts", "Environment Agency", "event_driven", "alerts"),
        "modis_burned_area": ("MODIS burned area", "NASA Earthdata AppEEARS", "daily", "hectares"),
        "desnz_fuel_prices": ("UK road fuel prices · DESNZ", "Department for Energy Security and Net Zero", "weekly", "pence_per_litre"),
        "ons_cost_pressures": ("ONS consumer prices · CPI", "Office for National Statistics", "monthly", "index_2015_100"),
        "brent_oil": ("Brent crude spot price", "FRED / U.S. EIA", "daily", "usd_per_barrel"),
        "market_prices": ("Company closing share prices", "Yahoo Finance chart endpoint", "daily", "local_currency_per_share"),
    }
    for source, (label, provider, cadence, unit) in optional_definitions.items():
        if source in bundles:
            definitions.append({"layer_id": source, "label": label, "provider": provider, "cadence": cadence, "geography": "market" if source in {"brent_oil", "market_prices"} else "GB", "units": [unit], "status": "adapter_ready", "source_url": bundles[source][0].get("source_snapshot", {}).get("endpoint"), "access_requirement": "Provider access and terms review", "independence_note": "Source-specific context retained separately from attention.", "release_id": release_id})
    from .contracts import DataLayerDefinition
    definitions = [DataLayerDefinition.model_validate(item).model_dump(mode="json") for item in definitions]
    snapshots_by_source = {item["source"]: item["snapshot_id"] for item in snapshots}
    data: dict[str, Any] = {
        "release": DatasetRelease(
            release_id=release_id, created_at=created_at, date_start=start, date_end=end,
            configuration_version="uk-pilot-v1", configuration_hash=release_config_hash(CONFIG),
            configuration_files=release_config_hashes(CONFIG), source_snapshots=snapshots_by_source,
            parquet_outputs=[],
            supabase_rows={"daily_attention": 0, "article_records": 0, "events": len(events),
                           "physical_observations": len(physical), "layer_observations": len(weather)},
            frontend_assets=["frontend/public/data/candidate.json"], status="candidate",
            methodology_note="Physical and economic context only. News and Bluesky attention are unavailable in this candidate. MODIS raw NDVI and greenness anomalies use a UK calendar-month 2001–2020 baseline; FIRMS detections are not wildfires; market closes are exploratory context. Associations do not establish causality.",
        ).model_dump(mode="json"),
        "daily_attention": [], "news_denominators": [], "articles": [], "social_posts": [],
        "physical_observations": physical, "events": events, "data_layers": weather,
        "source_snapshots": snapshots, "layer_definitions": definitions,
        "metadata": {"panel_definition": "No live monitored panel collected", "article_denominator": "Unavailable",
                     "source_bundle_sha256": source_hashes,
                     "review_status": "candidate; physical and event context only",
                     "flood_snapshot_is_current_only": "environment_agency_alerts" in bundles},
    }
    data["release"]["content_hash"] = release_content_hash(data)
    return data


def candidate_quality_report(data: dict[str, Any]) -> dict[str, Any]:
    errors = list(audit_release(data)["errors"])
    release = data.get("release", {})
    if release.get("status") != "candidate":
        errors.append("release must be a candidate")
    if release.get("content_hash") != release_content_hash(data):
        errors.append("candidate content hash is invalid")
    if data.get("daily_attention") or data.get("news_denominators") or data.get("social_posts") or data.get("articles"):
        errors.append("candidate must not contain synthetic or uncollected attention")
    if not any(item.get("metric") == "ndvi" for item in data.get("physical_observations", [])):
        errors.append("candidate has no real NDVI observation")
    if not data.get("data_layers"):
        errors.append("candidate has no temperature observations")
    layers = layer_quality_report({"observations": data.get("data_layers", []), "source_snapshots": data.get("source_snapshots", [])})
    errors.extend(layers["unit_errors"])
    if layers["duplicate_keys"] or layers["missing_snapshots"]:
        errors.append("candidate layer keys or snapshots are invalid")
    return {"status": "pass" if not errors else "fail", "errors": errors,
            "release_id": release.get("release_id"), "physical_rows": len(data.get("physical_observations", [])),
            "temperature_rows": len(data.get("data_layers", [])), "event_rows": len(data.get("events", [])),
            "source_snapshots": len(data.get("source_snapshots", []))}


def write_candidate(data: dict[str, Any], path: Path) -> Path:
    return write_json(data, path)
