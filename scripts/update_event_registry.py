#!/usr/bin/env python3
"""Refresh the GDACS portion of the reviewed event registry.

The curated entries (storms, COPs, conflicts and economic context) remain in
config/events.uk-pilot.yaml.  This script replaces only provider-derived GDACS
rows from a Wildfire-Trends/GeoJSON export, so a source refresh cannot erase a
manual review decision.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


UK_BOUNDS = (-8.7, 49.5, 2.5, 60.9)
EU_FIRE_COUNTRIES = {"FRA", "ESP", "PRT", "ITA", "GRC"}
START = "2021-09-01"
END = "2026-10-01"


def _in_period(value: str, start: str, end: str) -> bool:
    day = value[:10]
    return start <= day <= end


def _uk_point(feature: dict[str, Any]) -> bool:
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    return (
        len(coordinates) >= 2
        and UK_BOUNDS[0] <= float(coordinates[0]) <= UK_BOUNDS[2]
        and UK_BOUNDS[1] <= float(coordinates[1]) <= UK_BOUNDS[3]
    )


def _gdacs_event(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature["properties"]
    countries = properties.get("countryIso3s", [])
    return {
        "event_id": properties["id"],
        "canonical_name": properties["name"],
        "event_type": properties["hazardType"],
        "source": "gdacs",
        "aliases": [],
        "start_at": properties["startAt"],
        "end_at": properties.get("endAt"),
        "geometry": feature.get("geometry"),
        "geography_ids": ["GB"] if "GBR" in countries else ["EU"],
        "country_codes": countries,
        "external_ids": {"gdacs": properties.get("sourceEventId", properties["id"])},
        "source_urls": ([properties["sourceUrl"]] if properties.get("sourceUrl") else []),
        "registry_version": "uk-events-v2",
    }


def select_gdacs(features: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for feature in features:
        properties = feature.get("properties", {})
        if not _in_period(str(properties.get("startAt", "")), start, end):
            continue
        countries = set(properties.get("countryIso3s", []))
        hazard = properties.get("hazardType")
        uk_hazard = hazard in {"flood", "wildfire"} and "GBR" in countries and _uk_point(feature)
        european_fire = hazard == "wildfire" and countries.intersection(EU_FIRE_COUNTRIES) and properties.get("alertLevel") in {"Orange", "Red"}
        if uk_hazard or european_fire:
            selected.append(_gdacs_event(feature))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Wildfire-Trends events.geojson export")
    parser.add_argument("--registry", type=Path, default=Path("config/events.uk-pilot.yaml"))
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    features = source.get("features")
    if not isinstance(features, list):
        raise SystemExit("source must be a GeoJSON FeatureCollection")
    document = yaml.safe_load(args.registry.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("events"), list):
        raise SystemExit("registry must contain an events list")
    curated = [event for event in document["events"] if event.get("source", "custom") != "gdacs"]
    events = sorted(curated + select_gdacs(features, args.start, args.end), key=lambda event: (event["start_at"], event["event_id"]))
    ids = [event["event_id"] for event in events]
    if len(ids) != len(set(ids)):
        raise SystemExit("source produced duplicate event IDs")
    output = {"schema_version": 1, "registry_version": "uk-events-v2", "events": events}
    if not args.dry_run:
        args.registry.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"selected {sum(event['source'] == 'gdacs' for event in events)} GDACS and {sum(event['source'] != 'gdacs' for event in events)} curated events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
