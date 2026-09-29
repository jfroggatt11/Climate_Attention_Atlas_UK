"""Versioned event and place registry loading for article resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .contracts import Event, Place


def _mapping(path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def load_event_registry(path: str | Path) -> tuple[str, list[Event]]:
    document = _mapping(path)
    version = str(document.get("registry_version", "events-v1"))
    events = [Event.model_validate(item) for item in document.get("events", [])]
    ids = [event.event_id for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("event registry contains duplicate event IDs")
    return version, events


def load_place_registry(path: str | Path) -> tuple[str, list[Place]]:
    document = _mapping(path)
    version = str(document.get("boundary_version", "places-v1"))
    places = [Place.model_validate(item) for item in document.get("places", [])]
    ids = [place.place_id for place in places]
    if len(ids) != len(set(ids)):
        raise ValueError("place registry contains duplicate place IDs")
    return version, places
