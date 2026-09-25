import json

from climate_attention.economic import (
    collect_brent,
    collect_desnz_fuel_prices,
    collect_market_prices,
    collect_ons_cpi,
)


class FakeResponse:
    def __init__(self, text="", payload=None):
        self.text = text
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses[url]
        return response() if callable(response) else response


def test_desnz_collector_normalises_weekly_csv(tmp_path):
    from climate_attention.economic import DESNZ_FUEL_CSV_URL

    client = FakeClient({DESNZ_FUEL_CSV_URL: FakeResponse(
        "title\nWeek commencing,ULSP (Unleaded Petrol),ULSD (Diesel)\n"
        "01/09/2026,139.2,151.4\n"
    )})
    output = collect_desnz_fuel_prices(output=tmp_path / "bundle.json", raw_dir=tmp_path / "raw", client=client)
    data = json.loads(output.read_text())
    assert len(data["records"]) == 2
    assert {row["series_id"] for row in data["records"]} == {"uk_petrol", "uk_diesel"}
    assert data["source_snapshot"]["status"] == "available"


def test_ons_collector_keeps_series_identity(tmp_path):
    from climate_attention.economic import ONS_CPI_URL

    payload = {"observations": [{"time": "2026-08-01", "value": "139.2"}]}
    client = FakeClient({
        ONS_CPI_URL.format(series="D7BT"): FakeResponse(payload=json.loads(json.dumps(payload))),
        ONS_CPI_URL.format(series="D7G7"): FakeResponse(payload={"observations": [{"time": "2026-08-01", "value": "3.4"}]}),
    })
    output = collect_ons_cpi(output=tmp_path / "bundle.json", raw_dir=tmp_path / "raw", client=client)
    data = json.loads(output.read_text())
    assert {row["series_id"] for row in data["records"]} == {"cpi_all_items", "cpi_annual_rate"}


def test_brent_and_market_collectors_preserve_provider_metadata(tmp_path):
    from climate_attention.economic import FRED_BRENT_URL, YAHOO_CHART_URL

    chart = {"chart": {"result": [{"timestamp": [1756684800], "indicators": {"quote": [{"close": [350.0]}]}, "meta": {"currency": "USD"}}]}}
    client = FakeClient({
        FRED_BRENT_URL: FakeResponse("DATE,DCOILBRENTEU\n2026-09-01,72.4\n"),
        YAHOO_CHART_URL.format(symbol="TSLA"): FakeResponse(payload=chart),
    })
    brent = json.loads(collect_brent(output=tmp_path / "brent.json", raw_dir=tmp_path / "brent-raw", client=client).read_text())
    market = json.loads(collect_market_prices(symbols=["TSLA"], output=tmp_path / "market.json", raw_dir=tmp_path / "market-raw", client=client).read_text())
    assert brent["records"][0]["unit"] == "usd_per_barrel"
    assert market["records"][0]["metadata"]["symbol"] == "TSLA"
