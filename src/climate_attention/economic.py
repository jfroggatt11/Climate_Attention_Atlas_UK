"""Small public-data collectors for economic and market context.

These series stay separate from attention measures.  The collectors retain the
provider response and a source snapshot so revisions, gaps and licensing notes
remain visible when a candidate release is assembled.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx


DESNZ_FUEL_CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/6ab12fd444ec1aa417346d54/"
    "CSV__2018_-__.csv"
)
ONS_CPI_URL = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{series}/mm23/data"
FRED_BRENT_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_date(value: Any) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty date")
    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d %b %Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported provider date: {value!r}")


def _number(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    text = text.replace("£", "").replace("$", "")
    if not text or text in {"-", "..", "na", "n/a", "null"}:
        return None
    return float(text)


def _record(source: str, series_id: str, metric: str, observed: date, value: float,
            unit: str, *, geography: str = "GB", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "record_id": f"{source}:{series_id}:{observed.isoformat()}",
        "date": observed.isoformat(),
        "series_id": series_id,
        "metric": metric,
        "geography": geography,
        "value": value,
        "unit": unit,
        "metadata": metadata or {},
    }


def _write_bundle(output: Path, *, source: str, records: list[dict[str, Any]],
                  snapshot: dict[str, Any], raw_path: Path | None = None,
                  provider_metadata: dict[str, Any] | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {
        "schema_version": 1,
        "source": source,
        "collected_at": _now().isoformat(),
        "records": records,
        "source_snapshot": snapshot,
    }
    if raw_path is not None:
        bundle["raw_response"] = {"path": str(raw_path), "sha256": _sha256(raw_path)}
    if provider_metadata:
        bundle["provider_metadata"] = provider_metadata
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return output


def _snapshot(source: str, records: list[dict[str, Any]], *, endpoint: str, notes: str,
              request_count: int = 1, status: str = "available") -> dict[str, Any]:
    observed = sorted(row["date"] for row in records)
    return {
        "source": source,
        "snapshot_id": f"{source}-{_now().strftime('%Y%m%dT%H%M%SZ')}",
        "release_id": f"live-{source}-{_now().strftime('%Y%m%dT%H%M%SZ')}",
        "status": status,
        "observed_start": observed[0] if observed else None,
        "observed_end": observed[-1] if observed else None,
        "retrieved_at": _now().isoformat(),
        "endpoint": endpoint,
        "request_count": request_count,
        "completeness": 1.0 if records else 0.0,
        "notes": notes,
    }


def collect_desnz_fuel_prices(*, output: Path, raw_dir: Path,
                              client: httpx.Client | None = None) -> Path:
    """Collect the official weekly UK petrol and diesel price CSV."""
    owns = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        response = client.get(DESNZ_FUEL_CSV_URL)
        response.raise_for_status()
        text = response.text
    finally:
        if owns:
            client.close()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "weekly-road-fuel-prices.csv"
    raw_path.write_text(text, encoding="utf-8")
    lines = text.splitlines()
    header_index = next((index for index, line in enumerate(lines) if "ULSP" in line.upper() or "PETROL" in line.upper()), None)
    if header_index is None:
        raise ValueError("DESNZ CSV has no petrol price header")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    fieldnames = [field or "" for field in (reader.fieldnames or [])]
    date_field = next((field for field in fieldnames if any(token in field.lower() for token in ("date", "week", "commencing"))), fieldnames[0])
    petrol_field = next((field for field in fieldnames if "ulsp" in field.lower() or "petrol" in field.lower()), None)
    diesel_field = next((field for field in fieldnames if "ulsd" in field.lower() or "diesel" in field.lower()), None)
    if not petrol_field or not diesel_field:
        raise ValueError(f"DESNZ CSV columns do not contain petrol and diesel: {fieldnames}")
    records: list[dict[str, Any]] = []
    for row in reader:
        try:
            observed = _parse_date(row.get(date_field))
        except ValueError:
            continue
        for series_id, metric, field in (("uk_petrol", "petrol_pump_price", petrol_field), ("uk_diesel", "diesel_pump_price", diesel_field)):
            value = _number(row.get(field))
            if value is not None:
                records.append(_record("desnz_fuel_prices", series_id, metric, observed, value, "pence_per_litre", metadata={"fuel": series_id.removeprefix("uk_"), "cadence": "weekly"}))
    snapshot = _snapshot("desnz_fuel_prices", records, endpoint=DESNZ_FUEL_CSV_URL, notes="Official DESNZ weekly UK average pump prices; revisions are possible.")
    return _write_bundle(output, source="desnz_fuel_prices", records=records, snapshot=snapshot, raw_path=raw_path)


def _ons_rows(payload: Any) -> Iterable[tuple[date, float]]:
    if isinstance(payload, dict):
        date_value = payload.get("date") or payload.get("time") or payload.get("period")
        # The ONS website time-series endpoint returns parallel years,
        # quarters and months arrays. Only promote monthly rows here.
        if payload.get("month") and payload.get("year"):
            month_text = str(payload["month"]).strip()
            try:
                month_number = datetime.strptime(month_text[:3], "%b").month
                date_value = f"{payload['year']}-{month_number:02d}-01"
            except ValueError:
                date_value = None
        elif isinstance(date_value, str) and re.fullmatch(r"\d{4}", date_value.strip()):
            date_value = None
        elif isinstance(date_value, str) and re.fullmatch(r"\d{4} Q[1-4]", date_value.strip()):
            date_value = None
        value = _number(payload.get("value"))
        if date_value is not None and value is not None:
            try:
                yield _parse_date(date_value), value
            except ValueError:
                pass
        for child in payload.values():
            yield from _ons_rows(child)
    elif isinstance(payload, list):
        for child in payload:
            yield from _ons_rows(child)


def collect_ons_cpi(*, output: Path, raw_dir: Path,
                    client: httpx.Client | None = None) -> Path:
    """Collect ONS CPI index and annual-rate time series (no API key)."""
    owns = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    endpoints = (("D7BT", "cpi_all_items", "consumer_price_index", "index_2015_100"), ("D7G7", "cpi_annual_rate", "consumer_price_annual_rate", "percent_change_yoy"))
    try:
        for series, series_id, metric, unit in endpoints:
            response = client.get(ONS_CPI_URL.format(series=series))
            response.raise_for_status()
            raw_path = raw_dir / f"ons-{series.lower()}.json"
            raw_path.write_text(response.text, encoding="utf-8")
            payload = response.json()
            for observed, value in sorted(set(_ons_rows(payload))):
                records.append(_record("ons_cost_pressures", series_id, metric, observed, value, unit, metadata={"ons_series": series, "dataset": "MM23"}))
    finally:
        if owns:
            client.close()
    snapshot = _snapshot("ons_cost_pressures", records, endpoint="https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{series}/mm23/data", notes="ONS CPI time series MM23; ONS revisions and release vintages are retained at raw-response level.", request_count=2)
    return _write_bundle(output, source="ons_cost_pressures", records=records, snapshot=snapshot, raw_path=None, provider_metadata={"raw_dir": str(raw_dir), "series": ["D7BT", "D7G7"]})


def _fred_rows(text: str, column: str) -> Iterable[tuple[date, float]]:
    for row in csv.DictReader(io.StringIO(text)):
        value = _number(row.get(column))
        date_value = row.get("DATE") or row.get("observation_date")
        if value is not None and date_value:
            yield _parse_date(date_value), value


def collect_brent(*, output: Path, raw_dir: Path,
                  client: httpx.Client | None = None) -> Path:
    """Collect daily Brent spot price from the public FRED CSV export."""
    owns = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        response = client.get(FRED_BRENT_URL)
        response.raise_for_status()
        text = response.text
    finally:
        if owns:
            client.close()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "fred-dcoilbrenteu.csv"
    raw_path.write_text(text, encoding="utf-8")
    records = [_record("brent_oil", "brent_spot", "brent_price", observed, value, "usd_per_barrel", geography="market", metadata={"fred_series": "DCOILBRENTEU"}) for observed, value in _fred_rows(text, "DCOILBRENTEU")]
    snapshot = _snapshot("brent_oil", records, endpoint=FRED_BRENT_URL, notes="FRED daily Europe Brent spot price; values are market context, not UK pump prices.")
    return _write_bundle(output, source="brent_oil", records=records, snapshot=snapshot, raw_path=raw_path)


def collect_market_prices(*, symbols: list[str], output: Path, raw_dir: Path,
                          start: date | None = None, end: date | None = None,
                          client: httpx.Client | None = None) -> Path:
    """Collect daily closes from Yahoo's chart endpoint for exploratory market context.

    This adapter is intentionally marked as a market-data source and should not
    be published until T&E confirms the provider's redistribution terms.
    """
    owns = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "UK-Attention-Atlas/0.1"})
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    try:
        for symbol in symbols:
            response = client.get(YAHOO_CHART_URL.format(symbol=symbol), params={"range": "10y", "interval": "1d", "events": "history"})
            response.raise_for_status()
            raw_path = raw_dir / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', symbol)}.json"
            raw_path.write_text(response.text, encoding="utf-8")
            chart = response.json().get("chart", {})
            result = (chart.get("result") or [None])[0]
            if not result:
                raise ValueError(f"Yahoo chart returned no result for {symbol}")
            timestamps = result.get("timestamp") or []
            quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            closes = quote.get("close") or []
            currency = ((result.get("meta") or {}).get("currency") or "unknown").lower()
            series_id = symbol.lower().replace(".", "_")
            for timestamp, close in zip(timestamps, closes, strict=False):
                if close is None:
                    continue
                observed = datetime.fromtimestamp(int(timestamp), timezone.utc).date()
                if start and observed < start or end and observed > end:
                    continue
                records.append(_record("market_prices", series_id, "stock_close", observed, float(close), "local_currency_per_share", geography="market", metadata={"symbol": symbol, "currency": currency, "provider": "Yahoo Finance chart endpoint"}))
    finally:
        if owns:
            client.close()
    snapshot = _snapshot("market_prices", records, endpoint=YAHOO_CHART_URL, notes="Exploratory daily market closes. Confirm Yahoo Finance redistribution terms before publication.", request_count=len(symbols))
    return _write_bundle(output, source="market_prices", records=records, snapshot=snapshot, raw_path=None, provider_metadata={"symbols": symbols, "raw_dir": str(raw_dir)})
