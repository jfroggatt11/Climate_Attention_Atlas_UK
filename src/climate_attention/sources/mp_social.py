"""Import aggregate UK MP social-post counts from Sheets or XLSX exports.

The source is intentionally limited to classified post counts. Engagement
counters are not part of the atlas measure because their availability differs
by platform and can make cross-platform comparisons misleading.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zipfile import ZipFile
from xml.etree import ElementTree

from ..contracts import DailyAttention, QualityStatus, SourceSnapshot


SOURCE = "junkipedia_mp"
CATEGORY_TO_TOPIC = {
    "climate_change": "climate_change",
    "evs": "electric_vehicles",
    "fuel_prices": "fuel_prices",
    "extreme_weather": "extreme_weather",
}
REQUIRED_COLUMNS = ("level", "category", "grain", "period", "party", "platform", "posts")
IGNORED_ENGAGEMENT_COLUMNS = {
    "likes_sum", "likes_posts", "shares_sum", "shares_posts",
    "comments_sum", "comments_posts", "views_sum", "views_posts",
}
_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _utc(value: datetime | None = None) -> datetime:
    return value or datetime.now(timezone.utc)


def _number(value: Any, *, field: str, row_number: int) -> int:
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number} {field} must be numeric") from exc
    if not numeric.is_integer() or numeric < 0:
        raise ValueError(f"row {row_number} {field} must be a non-negative integer")
    return int(numeric)


def _period_date(value: Any, *, grain: str, row_number: int) -> date:
    text = str(value).strip()
    try:
        if grain == "day":
            return date.fromisoformat(text)
        if grain == "month":
            return date.fromisoformat(f"{text}-01")
        if grain == "year":
            return date.fromisoformat(f"{text}-01-01")
    except ValueError as exc:
        raise ValueError(f"row {row_number} has invalid {grain} period {text!r}") from exc
    raise ValueError(f"row {row_number} has unsupported grain {grain!r}")


def _header_rows(rows: Sequence[Sequence[Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    if not rows:
        raise ValueError("MP social-post sheet is empty")
    headers = [str(item).strip() for item in rows[0]]
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise ValueError(f"MP social-post sheet is missing columns: {', '.join(missing)}")
    records = []
    for row in rows[1:]:
        padded = list(row) + [None] * max(0, len(headers) - len(row))
        records.append({header: padded[index] for index, header in enumerate(headers)})
    return headers, records


def import_mp_social_rows(
    rows: Sequence[Sequence[Any]],
    *,
    release_id: str,
    collection_run_id: str,
    collected_at: datetime | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Normalize Google Sheets ``values`` or equivalent tabular rows.

    Only ``grain=day`` rows become serving observations. Month and year rows
    are retained as reconciliation controls and must agree with the day rows
    for each category, party and platform.
    """
    headers, raw_records = _header_rows(rows)
    collected = _utc(collected_at)
    seen: set[tuple[str, str, str, str, str, str]] = set()
    day_rows: list[dict[str, Any]] = []
    controls: dict[str, dict[tuple[str, str, str, str], int]] = {"month": {}, "year": {}}
    day_by_key: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    breakdown: list[dict[str, Any]] = []
    for row_number, row in enumerate(raw_records, start=2):
        grain = str(row.get("grain") or "").strip().lower()
        category = str(row.get("category") or "").strip()
        if str(row.get("level") or "").strip() != "party":
            raise ValueError(f"row {row_number} level must be 'party'")
        if category not in CATEGORY_TO_TOPIC:
            raise ValueError(f"row {row_number} has unsupported category {category!r}")
        period = _period_date(row.get("period"), grain=grain, row_number=row_number)
        party = str(row.get("party") or "").strip()
        platform = str(row.get("platform") or "").strip()
        if not party or not platform:
            raise ValueError(f"row {row_number} party and platform are required")
        posts = _number(row.get("posts"), field="posts", row_number=row_number)
        key = (grain, category, period.isoformat(), party, platform, SOURCE)
        if key in seen:
            raise ValueError(f"duplicate MP social-post row key at row {row_number}")
        seen.add(key)
        if grain == "day":
            day_key = (category, period.isoformat(), party, platform, SOURCE)
            day_by_key[day_key] = posts
            day_rows.append({"category": category, "topic_id": CATEGORY_TO_TOPIC[category], "date": period, "party": party, "platform": platform, "posts": posts})
        elif grain in controls:
            controls[grain][(category, period.isoformat(), party, platform)] = posts
        else:
            raise ValueError(f"row {row_number} has unsupported grain {grain!r}")

    for grain, expected in controls.items():
        for (category, period, party, platform), value in expected.items():
            if grain == "month":
                observed = sum(posts for (cat, day, pty, plt, _), posts in day_by_key.items() if cat == category and day[:7] == period[:7] and pty == party and plt == platform)
            else:
                observed = sum(posts for (cat, day, pty, plt, _), posts in day_by_key.items() if cat == category and day[:4] == period[:4] and pty == party and plt == platform)
            if observed != value:
                raise ValueError(f"{grain} control does not reconcile for {category}/{period}/{party}/{platform}: {value} vs {observed}")

    by_day_category: dict[tuple[str, date], int] = defaultdict(int)
    party_breakdowns: dict[tuple[str, date], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    platform_breakdowns: dict[tuple[str, date], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in day_rows:
        key = (row["category"], row["date"])
        by_day_category[key] += row["posts"]
        party_breakdowns[key][row["party"]] += row["posts"]
        platform_breakdowns[key][row["platform"]] += row["posts"]
        breakdown.append({"date": row["date"].isoformat(), "category": row["category"], "topic_id": row["topic_id"], "party": row["party"], "platform": row["platform"], "posts": row["posts"]})

    observations: list[dict[str, Any]] = []
    for (category, observed_day), count in sorted(by_day_category.items()):
        topic_id = CATEGORY_TO_TOPIC[category]
        attention = DailyAttention(
            date=observed_day,
            source=SOURCE,
            topic_id=topic_id,
            measure="count",
            value=float(count),
            unit="posts",
            denominator_definition="classified posts in the monitored UK MP candidate set; no all-post denominator is available",
            geography="GB",
            quality_status=QualityStatus.observed,
            completeness=None,
            observed_at=datetime(observed_day.year, observed_day.month, observed_day.day, tzinfo=timezone.utc),
            collected_at=collected,
            release_id=release_id,
            metadata={
                "raw_post_count": count,
                "grain": "day",
                "category": category,
                "party_breakdown": dict(sorted(party_breakdowns[(category, observed_day)].items())),
                "platform_breakdown": dict(sorted(platform_breakdowns[(category, observed_day)].items())),
                "collection_run_id": collection_run_id,
                "engagement_fields_ignored": sorted(IGNORED_ENGAGEMENT_COLUMNS & set(headers)),
                "source_scope": "Junkipedia UK MP channels; classified candidate posts",
            },
        )
        observations.append(attention.model_dump(mode="json"))

    snapshot = SourceSnapshot(
        source=SOURCE,
        snapshot_id=f"{SOURCE}-{collected.strftime('%Y%m%dT%H%M%SZ')}",
        status="available",
        observed_start=min((row["date"] for row in day_rows), default=None),
        observed_end=max((row["date"] for row in day_rows), default=None),
        retrieved_at=collected,
        endpoint=source_url,
        request_count=1,
        completeness=None,
        notes="Aggregate classified MP post counts imported at day grain; engagement counters are excluded.",
        release_id=release_id,
    )
    return {
        "source": SOURCE,
        "schema_version": 1,
        "source_snapshot": snapshot.model_dump(mode="json"),
        "records": observations,
        "daily_attention": observations,
        "breakdown": breakdown,
        "metadata": {
            "topic_mapping": CATEGORY_TO_TOPIC,
            "available_grains": sorted({str(row.get("grain")) for row in raw_records}),
            "engagement_fields_ignored": sorted(IGNORED_ENGAGEMENT_COLUMNS & set(headers)),
            "category_post_total": sum(by_day_category.values()),
        },
    }


def read_xlsx_values(path: str | Path, *, sheet_name: str = "engagement") -> list[list[str]]:
    """Read a simple XLSX value table without adding an Excel dependency."""
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//x:t", _NS)) for item in root.findall("x:si", _NS)]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        rel_targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships.findall("r:Relationship", rel_ns)}
        target = None
        for sheet in workbook.findall("x:sheets/x:sheet", _NS):
            if sheet.attrib.get("name") == sheet_name:
                target = rel_targets.get(sheet.attrib.get(f"{{{_NS['r']}}}id"))
                break
        if target is None:
            raise ValueError(f"XLSX sheet {sheet_name!r} not found")
        sheet_path = target.lstrip("/") if target.startswith("/xl/") or target.startswith("xl/") else "xl/" + target.lstrip("/")
        root = ElementTree.fromstring(archive.read(sheet_path))
        output: list[list[str]] = []
        for row in root.findall("x:sheetData/x:row", _NS):
            cells: dict[int, str] = {}
            for cell in row.findall("x:c", _NS):
                ref = cell.attrib.get("r", "A1")
                column = 0
                for char in ref:
                    if not char.isalpha():
                        break
                    column = column * 26 + ord(char.upper()) - 64
                column -= 1
                value = cell.find("x:v", _NS)
                text = value.text if value is not None else ""
                if cell.attrib.get("t") == "s" and text:
                    text = shared[int(text)]
                elif cell.attrib.get("t") == "inlineStr":
                    text = "".join(node.text or "" for node in cell.findall(".//x:t", _NS))
                cells[column] = text
            output.append([cells.get(index, "") for index in range(max(cells.keys(), default=-1) + 1)])
        return output
