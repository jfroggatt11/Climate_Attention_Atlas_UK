"""Load and validate the reviewed outlet and Bluesky seed panels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .contracts import AccountPanelEntry, OutletRegistryEntry


def _load(path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def load_outlet_registry(path: str | Path) -> list[OutletRegistryEntry]:
    return [OutletRegistryEntry.model_validate(item) for item in _load(path).get("outlets", [])]


def resolve_outlet(domain: str, registry: list[OutletRegistryEntry]) -> OutletRegistryEntry | None:
    """Resolve a host conservatively, preferring the longest reviewed domain."""
    host = domain.strip().lower().split(":", 1)[0].lstrip(".")
    candidates = [
        item for item in registry
        if item.domain.lower() == host
        or host.endswith("." + item.domain.lower())
        or any(host == alias.lower() or host.endswith("." + alias.lower()) for alias in item.domain_aliases)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: len(item.domain))


def load_account_panel(path: str | Path) -> list[AccountPanelEntry]:
    return [AccountPanelEntry.model_validate(item) for item in _load(path).get("accounts", [])]
