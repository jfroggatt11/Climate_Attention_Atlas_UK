"""Small, auditable live-data collectors.

Collectors write a source-separated JSON bundle.  The bundle is intentionally
independent from the checked-in fixture release: a live run must be reviewed
before it can become a published release.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
import re
from urllib.parse import urlparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Country, load_country_config
from .source_layers import parse_json_observations


EA_FLOODS_URL = "https://environment.data.gov.uk/flood-monitoring/id/floods"
HADUK_BASE_URL = "https://www.metoffice.gov.uk/hadobs/hadukgrid/data"
HADUK_CEDA_ROOT = "https://data.ceda.ac.uk/badc/ukmo-hadobs/data/insitu/MOHC/HadOBS/HadUK-Grid"
NATURAL_EARTH_COUNTRIES_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dotenv_value(name: str) -> str:
    """Read a project .env value without printing or mutating credentials."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw or raw.lstrip().startswith("#"):
            continue
        key, candidate = raw.split("=", 1)
        if key.strip() == name:
            return candidate.strip().strip('"').strip("'")
    return ""


def _ceda_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    token = _dotenv_value("CEDA_ACCESS_TOKEN") or _dotenv_value("CEDA_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError(f"CEDA listing is not a directory response: {url}")
    return payload


def ensure_country_boundaries(path: Path) -> Path:
    """Download the public Natural Earth sovereign polygons when absent."""
    if path.exists() and path.stat().st_size:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with urllib.request.urlopen(NATURAL_EARTH_COUNTRIES_URL, timeout=120) as response:
        temporary.write_bytes(response.read())
    os.replace(temporary, path)
    return path


def resolve_latest_haduk_country_url(*, target_year: int | None = None) -> str:
    """Discover the newest CEDA country-area monthly tas NetCDF file."""
    root = _ceda_json(f"{HADUK_CEDA_ROOT}/?json=")
    versions = [
        item for item in root["items"]
        if item.get("type") == "dir" and re.fullmatch(r"v\d+\.\d+\.\d+\.ceda", str(item.get("name", "")))
    ]
    if not versions:
        raise ValueError("CEDA HadUK-Grid archive has no version directories")
    versions.sort(key=lambda item: tuple(int(part) for part in re.findall(r"\d+", item["name"])))
    version = versions[-1]["name"]
    listing = _ceda_json(f"{HADUK_CEDA_ROOT}/{version}/country/tas/mon/?json=")
    # A monthly country release is normally one file under a dated vYYYYMMDD
    # directory. Select the file covering the requested year when possible.
    release_dirs = [item for item in listing["items"] if item.get("type") == "dir"]
    release_dirs.sort(key=lambda item: str(item.get("name", "")), reverse=True)
    candidates: list[dict[str, Any]] = []
    for release in release_dirs:
        sub = _ceda_json(f"{HADUK_CEDA_ROOT}/{version}/country/tas/mon/{release['name']}/?json=")
        candidates.extend(item for item in sub["items"] if str(item.get("name", "")).endswith(".nc"))
    if not candidates:
        raise ValueError("CEDA HadUK-Grid tas monthly archive contains no NetCDF files")
    pattern = re.compile(r"_(\d{4})\d{4}-(\d{4})\d{4}\.nc$")
    if target_year is not None:
        covering = [item for item in candidates if (match := pattern.search(str(item.get("name", "")))) and int(match.group(1)) <= target_year <= int(match.group(2))]
        if covering:
            candidates = covering
    selected = max(candidates, key=lambda item: str(item.get("name", "")))
    return f"https://dap.ceda.ac.uk{selected['path']}?download=1"


def _write_bundle(output: Path, *, source: str, records: list[dict[str, Any]],
                  snapshot: dict[str, Any], raw_path: Path | None = None,
                  provider_metadata: dict[str, Any] | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "schema_version": 1,
        "source": source,
        "collected_at": _now().isoformat(),
        "records": records,
        "source_snapshot": snapshot,
    }
    if provider_metadata:
        bundle["provider_metadata"] = provider_metadata
    if raw_path is not None:
        bundle["raw_response"] = {
            "path": str(raw_path),
            "sha256": _sha256(raw_path),
        }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    return output


def collect_environment_agency_floods(*, output: Path, raw_dir: Path,
                                      client: httpx.Client | None = None) -> Path:
    """Capture the current England flood-warning feed (a snapshot, not history)."""
    owns = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        response = client.get(EA_FLOODS_URL, params={"_view": "full"})
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns:
            client.close()
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    raw_path = raw_dir / f"environment_agency_floods_{stamp}.json"
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    raw_records: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        severity = item.get("severity") or item.get("floodWarningType")
        area = item.get("floodArea") or {}
        if not isinstance(area, dict):
            area = {}
        raw_records.append({
            "id": item.get("@id"),
            "date": _now().date().isoformat(),
            "value": 1,
            "metadata": {"severity": severity, "description": item.get("description"), "county": area.get("county")},
        })
    records = [item.model_dump(mode="json") for item in parse_json_observations(
        raw_records,
        source="environment_agency_alerts",
        series_id="flood_alerts",
        metric="flood_alert_count",
        unit="alerts",
        geography="GB",
        geography_level="region",
        run_id=f"ea-floods-{stamp}",
        release_id=f"live-ea-floods-{stamp}",
    )]
    snapshot = {
        "source": "environment_agency_alerts",
        "snapshot_id": f"ea-floods-{stamp}",
        "release_id": f"live-ea-floods-{stamp}",
        "status": "partial",
        "retrieved_at": _now().isoformat(),
        "endpoint": EA_FLOODS_URL,
        "request_count": 1,
        "completeness": 1.0,
        "notes": "Current Environment Agency flood warnings and alerts for England; this endpoint does not provide historical daily backfill.",
    }
    return _write_bundle(output, source="environment_agency_alerts", records=records, snapshot=snapshot, raw_path=raw_path)


def collect_gdacs(*, start: date, end: date, output: Path, cache_dir: Path,
                  countries: list[Country]) -> Path:
    """Collect GDACS major flood, wildfire and tropical-cyclone events."""
    from .sources.gdacs import GDACSProvider

    with GDACSProvider(countries=countries, cache_dir=cache_dir) as provider:
        events, requests = provider.collect(start, end)
    records = [event.model_dump(mode="json") for event in events]
    snapshot = {
        "source": "gdacs",
        "snapshot_id": f"gdacs-{start.isoformat()}-{end.isoformat()}",
        "release_id": f"live-gdacs-{start.isoformat()}-{end.isoformat()}",
        "status": "available",
        "observed_start": start.isoformat(),
        "observed_end": end.isoformat(),
        "retrieved_at": _now().isoformat(),
        "endpoint": "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/search",
        "request_count": len(requests),
        "completeness": 1.0,
        "notes": "Free catalogue of major events. Events are filtered to configured country ISO3 mappings; unmatched countries remain in event metadata.",
    }
    return _write_bundle(output, source="gdacs", records=records, snapshot=snapshot, provider_metadata={"requests": requests})


def haduk_country_url(year: int, *, variable: str = "tas") -> str:
    """Return the documented Met Office annual country-area file URL."""
    return f"{HADUK_BASE_URL}/{year}/{variable}_hadukgrid_uk_country_mon_{year}0101-{year}1231.nc"


def collect_haduk_country(*, year: int, output: Path, raw_dir: Path,
                          url: str | None = None, input_path: Path | None = None) -> Path:
    """Download and normalise one annual HadUK-Grid country-area file.

    ``xarray`` and a NetCDF engine are optional dependencies because most runs
    only use the social/event collectors.  The parser accepts either a scalar
    country series or a country dimension with a ``United Kingdom``/``GB``
    coordinate.
    """
    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - optional live extra
        raise RuntimeError("install the live extra to read HadUK-Grid NetCDF (xarray and a NetCDF engine)") from exc
    source_url = url or resolve_latest_haduk_country_url(target_year=year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = input_path or (raw_dir / Path(urlparse(source_url).path).name)
    if input_path is not None and not path.exists():
        raise FileNotFoundError(path)
    if input_path is None and not path.exists():
        request = urllib.request.Request(source_url)
        token = _dotenv_value("CEDA_ACCESS_TOKEN") or _dotenv_value("CEDA_TOKEN")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as handle:
            handle.write(response.read())
    dataset = xr.open_dataset(path)
    try:
        if "tas" not in dataset:
            raise ValueError(f"HadUK file has no tas variable: {sorted(dataset.data_vars)}")
        variable = dataset["tas"]
        # Country files commonly expose a country/region coordinate. Keep the
        # selection explicit so a future multi-country file cannot be widened.
        for dim in variable.dims:
            if dim not in {"time", "month", "date"} and variable.sizes[dim] > 1:
                labels_coord = dataset.get("geo_region") if "geo_region" in dataset else dataset[dim]
                labels = [str(value, "utf-8") if isinstance(value, bytes) else str(value) for value in labels_coord.values]
                selected_index = next((index for index, label in enumerate(labels) if label.strip().casefold() in {"gb", "gbr", "united kingdom", "uk"}), None)
                if selected_index is None:
                    raise ValueError(f"cannot identify United Kingdom in HadUK dimension {dim}: {labels}")
                variable = variable.isel({dim: selected_index})
        values = variable.values.reshape(-1)
        times = dataset["time"].values if "time" in dataset else []
        if len(times) != len(values):
            raise ValueError("HadUK tas and time dimensions do not align")
        raw_records = []
        for timestamp, value in zip(times, values):
            if value != value:  # NaN
                continue
            observed = str(timestamp)[:10]
            raw_records.append({"id": f"haduk_grid_{observed}", "date": observed, "value": float(value), "metadata": {"variable": "tas", "unit": "degrees_celsius", "resolution": "country", "licence": "Open Government Licence"}})
    finally:
        dataset.close()
    records = [item.model_dump(mode="json") for item in parse_json_observations(
        raw_records,
        source="haduk_grid_weather",
        series_id="uk_tas",
        metric="temperature",
        unit="degrees_celsius",
        geography="GB",
        geography_level="country",
        run_id=f"haduk-country-{year}",
        release_id=f"live-haduk-country-{year}",
    )]
    snapshot = {
        "source": "haduk_grid_weather",
        "snapshot_id": f"haduk-country-{year}",
        "release_id": f"live-haduk-country-{year}",
        "status": "available",
        "observed_start": records[0]["observed_at"][:10] if records else None,
        "observed_end": records[-1]["observed_at"][:10] if records else None,
        "retrieved_at": _now().isoformat(),
        "endpoint": source_url if input_path is None else f"file://{path}",
        "request_count": 1,
        "completeness": 1.0 if records else 0.0,
        "notes": "Met Office HadUK-Grid country area average; provisional files may be revised.",
    }
    return _write_bundle(output, source="haduk_grid_weather", records=records, snapshot=snapshot, raw_path=path)


def load_live_countries(path: Path) -> list[Country]:
    return load_country_config(path).enabled_countries()


def _annotate_modis_ndvi_anomalies(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach the old repo's UK 2001–2020 calendar-month NDVI baseline.

    The satellite observation remains the live value.  The baseline is a small,
    versioned reference table so an anomaly can be calculated reproducibly when
    a new MOD13C2 month arrives, without pretending that the current-year
    snapshot is itself a climatology.
    """
    baseline_path = Path(__file__).resolve().parents[2] / "data/reference/modis_ndvi_uk_baseline_2001_2020.json"
    if not baseline_path.is_file():
        return records
    try:
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline = {int(item["month"]): item for item in payload.get("months", [])}
        baseline_sha256 = _sha256(baseline_path)
    except (OSError, TypeError, ValueError, KeyError):
        return records
    for row in records:
        if row.get("country_iso3") not in (None, "GBR"):
            continue
        try:
            month = date.fromisoformat(str(row["date"])[:10]).month
            climatology = baseline[month]
            value = float(row["value"])
            mean = float(climatology["mean"])
            std = float(climatology["std"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        row["anomaly"] = value - mean
        row["standardized_anomaly"] = (value - mean) / std if std else None
        row["baseline_start_year"] = int(payload["baseline_start_year"])
        row["baseline_end_year"] = int(payload["baseline_end_year"])
        row.setdefault("metadata", {}).update({
            "anomaly_baseline": "calendar-month UK MODIS climatology",
            "baseline_start_year": row["baseline_start_year"],
            "baseline_end_year": row["baseline_end_year"],
            "baseline_sample_count": climatology.get("sample_count"),
            "baseline_reference": str(baseline_path),
            "baseline_reference_sha256": baseline_sha256,
        })
    return records


def collect_modis_ndvi(*, start: date, end: date, output: Path, raw_dir: Path,
                       boundary_geojson: Path, countries: list[Country]) -> Path:
    """Fetch monthly MOD13C2 NDVI and calculate country means for configured countries."""
    try:
        import earthaccess
        from .geography import load_country_boundaries
        from .satellite import (discover_mod13c2_granules, download_mod13c2_subset,
                                mod13c2_country_observations, parse_mod13c2_date,
                                read_mod13c2_subset)
    except ImportError as exc:  # pragma: no cover - optional live extra
        raise RuntimeError("install the live extra to collect MODIS NDVI (earthaccess, rasterio, pycountry, numpy)") from exc
    earthdata_token = _dotenv_value("EARTHDATA_TOKEN")
    earthdata_username = _dotenv_value("EARTHDATA_USERNAME")
    earthdata_password = _dotenv_value("EARTHDATA_PASSWORD")
    if not (earthdata_token or (earthdata_username and earthdata_password)):
        raise RuntimeError("set EARTHDATA_TOKEN, or EARTHDATA_USERNAME and EARTHDATA_PASSWORD; do not put credentials in the repository")
    # earthaccess reads these from the process environment. Load values from
    # the project dotenv file only for this process; they are never persisted.
    for name, value in (("EARTHDATA_TOKEN", earthdata_token), ("EARTHDATA_USERNAME", earthdata_username), ("EARTHDATA_PASSWORD", earthdata_password)):
        if value and not os.environ.get(name):
            os.environ[name] = value
    earthaccess.login(strategy="environment")
    session = earthaccess.get_requests_https_session()
    boundaries = load_country_boundaries(ensure_country_boundaries(boundary_geojson), countries)
    granules = discover_mod13c2_granules(start, end)
    records: list[dict[str, Any]] = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    for granule_id in granules:
        path = raw_dir / f"{granule_id}_ndvi.nc4"
        download_mod13c2_subset(session, granule_id, path, metric="ndvi")
        values = read_mod13c2_subset(path)
        observed = parse_mod13c2_date(granule_id)
        records.extend(item.model_dump(mode="json") for item in mod13c2_country_observations(values, boundaries=boundaries, observed=observed, granule_id=granule_id, metric="ndvi"))
    _annotate_modis_ndvi_anomalies(records)
    snapshot = {
        "source": "modis_mod13c2",
        "snapshot_id": f"mod13c2-ndvi-{start.isoformat()}-{end.isoformat()}",
        "release_id": f"live-mod13c2-ndvi-{start.isoformat()}-{end.isoformat()}",
        "status": "available" if records else "partial",
        "observed_start": min((item["date"] for item in records), default=None),
        "observed_end": max((item["date"] for item in records), default=None),
        "retrieved_at": _now().isoformat(),
        "endpoint": "https://opendap.earthdata.nasa.gov/collections/C2565788914-LPCLOUD/granules",
        "request_count": len(granules),
        "completeness": 1.0 if records else 0.0,
        "notes": "NASA MOD13C2 v061 monthly NDVI; country means are latitude-area-weighted over valid 0.05-degree cells. Greenness anomalies use the UK calendar-month 2001–2020 baseline carried forward from the old Wildfire-Trends pipeline.",
    }
    return _write_bundle(output, source="modis_mod13c2", records=records, snapshot=snapshot, provider_metadata={"granules": granules})


def collect_modis_burned_area(*, start: date, end: date, output: Path, raw_dir: Path,
                              boundary_geojson: Path, countries: list[Country]) -> Path:
    """Submit an authenticated AppEEARS MCD64A1 Burn_Date task and normalize UK hectares.

    AppEEARS is asynchronous, so the task ID is retained in the bundle metadata.
    The raw rasters remain in the ignored live directory for audit and reruns.
    """
    from .geography import load_country_boundaries
    from .satellite import (
        AppEEARSClient,
        MODIS_BURNED_AREA_PRODUCT,
        MODIS_BURN_DATE_LAYER,
        build_appeears_area_task,
        load_aid_map,
        parse_mcd64_burn_date_raster,
    )
    username = _dotenv_value("EARTHDATA_USERNAME")
    password = _dotenv_value("EARTHDATA_PASSWORD")
    if not username or not password:
        raise RuntimeError("MCD64 AppEEARS collection requires EARTHDATA_USERNAME and EARTHDATA_PASSWORD")
    boundaries = load_country_boundaries(ensure_country_boundaries(boundary_geojson), countries)
    task, aid_map = build_appeears_area_task(
        countries=countries, boundaries=boundaries, start=start, end=end,
        task_name=f"uk-atlas-mcd64-{start.isoformat()}-{end.isoformat()}",
        product=MODIS_BURNED_AREA_PRODUCT, layer=MODIS_BURN_DATE_LAYER,
    )
    aid_map_path = raw_dir / "aid-map.json"
    request_path = raw_dir / "appeears-task.json"
    from .satellite import write_appeears_task
    write_appeears_task(task, aid_map, request_path=request_path, aid_map_path=aid_map_path)
    with AppEEARSClient(username, password) as client:
        task_id = client.submit(task)
        client.wait(task_id)
        downloaded = client.download_support_files(task_id, raw_dir / task_id, include_burn_date_rasters=True)
    records: list[dict[str, Any]] = []
    aid_lookup = load_aid_map(aid_map_path)
    for path in downloaded:
        if "Burn_Date" not in path.name or not path.suffix.lower().endswith("tif"):
            continue
        for item in parse_mcd64_burn_date_raster(path, aid_map=aid_lookup):
            if item.country_iso3 != "GBR" or not (start <= item.date <= end):
                continue
            records.append({
                "record_id": item.record_id, "date": item.date.isoformat(),
                "series_id": "uk_burned_area", "metric": "burned_area",
                "geography": "GB", "value": item.value, "unit": "hectares",
                "metadata": {**item.metadata, "product": item.product, "country_iso3": item.country_iso3},
            })
    records.sort(key=lambda row: row["date"])
    snapshot = {
        "source": "modis_burned_area", "snapshot_id": f"mcd64-{task_id}",
        "release_id": f"live-mcd64-{start.isoformat()}-{end.isoformat()}",
        "status": "available" if records else "partial",
        "observed_start": min((row["date"] for row in records), default=None),
        "observed_end": max((row["date"] for row in records), default=None),
        "retrieved_at": _now().isoformat(),
        "endpoint": "https://appeears.earthdatacloud.nasa.gov/api/",
        "request_count": 1, "completeness": 1.0 if records else 0.0,
        "notes": "NASA MODIS MCD64A1.061 Burn_Date native-projection rasters converted to daily UK burned hectares; zero-burn days are retained when covered.",
    }
    return _write_bundle(output, source="modis_burned_area", records=records, snapshot=snapshot, provider_metadata={"task_id": task_id, "downloaded_files": [str(path) for path in downloaded]})


def collect_firms(*, start: date, end: date, output: Path, cache_dir: Path,
                  boundary_geojson: Path, countries: list[Country]) -> Path:
    """Collect NASA FIRMS vegetation-fire detections and UK country-day totals."""
    from .geography import load_country_boundaries
    from .sources.firms import FIRMSProvider, ensure_natural_earth_boundaries, firms_map_key

    boundaries_path = boundary_geojson
    if not boundaries_path.exists():
        boundaries_path = ensure_natural_earth_boundaries(boundaries_path)
    boundaries = load_country_boundaries(boundaries_path, countries)
    with FIRMSProvider(
        map_key=firms_map_key(),
        source="VIIRS_SNPP_SP",
        boundary_index=boundaries,
        countries=countries,
        cache_dir=cache_dir,
    ) as provider:
        rows, requests, totals = provider.collect(start, end)
    records = [item.model_dump(mode="json") for item in rows]
    snapshot = {
        "source": "firms",
        "snapshot_id": f"firms-{start.isoformat()}-{end.isoformat()}",
        "release_id": f"live-firms-{start.isoformat()}-{end.isoformat()}",
        "status": "available",
        "observed_start": start.isoformat(),
        "observed_end": end.isoformat(),
        "retrieved_at": _now().isoformat(),
        "endpoint": "https://firms.modaps.eosdis.nasa.gov/api/area/csv",
        "request_count": len(requests),
        "completeness": 1.0,
        "notes": "NASA FIRMS VIIRS_SNPP_SP world-area windows; low-confidence and non-vegetation detections are excluded, and detections are aggregated to configured country-days.",
    }
    return _write_bundle(output, source="firms", records=records, snapshot=snapshot, provider_metadata={"requests": requests, "totals": totals})
