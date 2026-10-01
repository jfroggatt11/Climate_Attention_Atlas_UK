"""Collector and parser for the DESNZ Public Attitudes Tracker.

The tracker publishes aggregate Excel workbooks rather than a respondent API.
This module keeps the published workbook and GOV.UK page snapshot alongside a
tidy, source-separated observation bundle so a later release can be compared
without overwriting the earlier one.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from openpyxl import load_workbook


DESNZ_PAT_COLLECTION_URL = "https://www.gov.uk/api/content/government/collections/public-attitudes-tracking-survey"
DESNZ_PAT_SOURCE = "desnz_pat"
_SEASON_MONTH = {"spring": 3, "summer": 6, "autumn": 9, "winter": 12}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value: str) -> str:
    value = value.lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "unknown"


def _wave_date(label: str) -> date | None:
    match = re.search(r"\b(Spring|Summer|Autumn|Winter)\s+(20\d{2})\b", label, re.I)
    if not match:
        return None
    return date(int(match.group(2)), _SEASON_MONTH[match.group(1).lower()], 1)


def _release_rank(value: str) -> tuple[int, int]:
    match = re.search(r"\b(Spring|Summer|Autumn|Winter)\s+(20\d{2})\b", value, re.I)
    if not match:
        return (0, 0)
    # Calendar ordering puts Winter after Autumn for release ranking.
    season_rank = {"spring": 1, "summer": 2, "autumn": 3, "winter": 4}
    return (int(match.group(2)), season_rank[match.group(1).lower()])


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, str) and value.strip().lower() in {"", "low", "-", "n/a", "na"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def discover_desnz_pat_release(*, client: httpx.Client | None = None) -> dict[str, Any]:
    """Return the newest statistics release and its time-series attachment."""
    owns = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        collection_response = client.get(DESNZ_PAT_COLLECTION_URL)
        collection_response.raise_for_status()
        collection = collection_response.json()
        documents = collection.get("links", {}).get("documents", [])
        candidates = [
            item for item in documents
            if str(item.get("title", "")).startswith("DESNZ Public Attitudes Tracker:")
            and "/government/statistics/" in str(item.get("base_path", ""))
        ]
        if not candidates:
            raise ValueError("DESNZ PAT collection has no statistics releases")
        candidates.sort(key=lambda item: _release_rank(str(item.get("title", ""))), reverse=True)
        page = candidates[0]
        page_path = str(page["base_path"])
        page_response = client.get(f"https://www.gov.uk/api/content{page_path}")
        page_response.raise_for_status()
        payload = page_response.json()
        attachments = payload.get("details", {}).get("attachments", [])
        timeseries = next(
            (item for item in attachments if item.get("attachment_type") == "file" and "time series" in str(item.get("title", "")).lower()),
            None,
        )
        if not timeseries or not timeseries.get("url"):
            raise ValueError(f"DESNZ PAT release {page_path} has no time-series workbook")
        questionnaire = next((item for item in attachments if "questionnaire" in str(item.get("title", "")).lower()), None)
        return {
            "release_title": page.get("title"), "release_page": f"https://www.gov.uk{page_path}",
            "page_path": page_path, "page_payload": payload,
            "time_series_url": timeseries["url"], "time_series_title": timeseries.get("title"),
            "questionnaire_url": (questionnaire or {}).get("url"),
            "published_at": payload.get("details", {}).get("first_public_at") or payload.get("first_published_at"),
        }
    finally:
        if owns:
            client.close()


def parse_desnz_pat_workbook(
    workbook_path: str | Path, *, release_id: str, collection_run_id: str,
    source_url: str | None = None,
) -> list[dict[str, Any]]:
    """Parse response rows from every question sheet in a PAT time-series workbook."""
    path = Path(workbook_path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    digest = _sha256(path)
    records: list[dict[str, Any]] = []
    for sheet in workbook.worksheets:
        if sheet.title.lower() == "table of contents":
            continue
        rows = sheet.iter_rows(values_only=True)
        first = next(rows, None)
        question_text_row = next(rows, None)
        question_text = question_text_row[0] if question_text_row else None
        # Rows 3-8 are notes. The table header is identified rather than relying
        # on a fixed row so a small cover-note change does not shift the parser.
        header = None
        for candidate in rows:
            if str(candidate[0] or "").strip().lower() == "subgroup identifier row":
                header = candidate
                break
        if header is None:
            continue
        wave_columns: list[tuple[int, str, date]] = []
        for index, value in enumerate(header[2:], start=2):
            wave = _wave_date(str(value or "").replace("\n", " "))
            if wave:
                wave_columns.append((index, str(value).replace("\n", " ").strip(), wave))
        if not wave_columns:
            continue
        table_rows = list(rows)
        by_label = {str(row[0]).strip().lower(): row for row in table_rows if row and row[0] is not None}
        unweighted = by_label.get("unweighted base")
        weighted = by_label.get("weighted base")
        question_id = sheet.title.strip()
        for row in table_rows:
            label = str(row[0] or "").strip()
            label_lower = label.lower()
            if not label or label_lower in {"unweighted base", "weighted base"}:
                continue
            for index, wave_label, observed in wave_columns:
                raw = row[index] if index < len(row) else None
                value = _number(raw)
                # PAT stores proportions in the workbook; the Atlas contract is percent.
                estimate = value * 100 if value is not None and 0 <= value <= 1 else value
                unweighted_n = _number(unweighted[index]) if unweighted and index < len(unweighted) else None
                weighted_base = _number(weighted[index]) if weighted and index < len(weighted) else None
                series_id = f"{_slug(question_id)}_{_slug(label)}"
                records.append({
                    "record_id": f"{DESNZ_PAT_SOURCE}:{series_id}:{observed.isoformat()}",
                    "date": observed.isoformat(), "series_id": series_id,
                    "metric": "survey_response_share", "geography": "UK",
                    "value": estimate, "unit": "percent",
                    "metadata": {
                        "question_id": question_id,
                        "question_text": str(question_text or "").strip(),
                        "response_label": label, "wave": wave_label,
                        "population": "adults_16_plus", "base_label": "All respondents",
                        "unweighted_n": unweighted_n, "weighted_base": weighted_base,
                        "mode": "online_and_paper", "source_url": source_url,
                        "workbook_sha256": digest,
                        "quality_status": "observed" if estimate is not None else "missing",
                    },
                })
    if not records:
        raise ValueError("DESNZ PAT workbook contained no recognisable question tables")
    return records


def collect_desnz_pat(*, output: Path, raw_dir: Path, client: httpx.Client | None = None) -> Path:
    """Discover, download and parse the latest DESNZ PAT time-series workbook."""
    owns = client is None
    client = client or httpx.Client(timeout=90, follow_redirects=True)
    try:
        release = discover_desnz_pat_release(client=client)
        workbook_response = client.get(release["time_series_url"])
        workbook_response.raise_for_status()
        raw_dir.mkdir(parents=True, exist_ok=True)
        release_id = f"desnz-pat-{_slug(release['release_title'])}"
        run_id = f"{release_id}-{_now().strftime('%Y%m%dT%H%M%SZ')}"
        workbook_path = raw_dir / Path(release["time_series_url"]).name
        workbook_path.write_bytes(workbook_response.content)
        landing_path = raw_dir / "release-page.json"
        landing_path.write_text(json.dumps(release["page_payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records = parse_desnz_pat_workbook(workbook_path, release_id=release_id, collection_run_id=run_id, source_url=release["release_page"])
        dates = sorted(row["date"] for row in records)
        retrieved = _now()
        bundle = {
            "schema_version": 1, "source": DESNZ_PAT_SOURCE, "release_id": release_id,
            "collection_run_id": run_id, "collected_at": retrieved.isoformat(), "records": records,
            "source_snapshot": {
                "source": DESNZ_PAT_SOURCE, "snapshot_id": f"{DESNZ_PAT_SOURCE}-{_sha256(workbook_path)[:12]}",
                "status": "available", "observed_start": dates[0], "observed_end": dates[-1],
                "retrieved_at": retrieved.isoformat(), "endpoint": release["release_page"],
                "request_count": 3, "completeness": 1.0,
                "notes": "DESNZ Public Attitudes Tracker aggregate time-series workbook; values are weighted response percentages. Low values are retained as missing.",
                "release_id": release_id,
            },
            "raw_response": {"workbook": str(workbook_path), "workbook_sha256": _sha256(workbook_path), "landing_page": str(landing_path), "landing_page_sha256": _sha256(landing_path)},
            "provider_metadata": {key: value for key, value in release.items() if key not in {"page_payload"}},
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
        return output
    finally:
        if owns:
            client.close()
