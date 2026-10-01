import json
from pathlib import Path

from openpyxl import Workbook

from climate_attention.polling import (
    DESNZ_PAT_COLLECTION_URL,
    collect_desnz_pat,
    parse_desnz_pat_workbook,
)


def _workbook(path: Path) -> None:
    book = Workbook()
    sheet = book.active
    sheet.title = "CLIMCONCERN"
    sheet.append(["Concern about climate change"])
    sheet.append(["CLIMCONCERN. How concerned are you?"])
    for _ in range(6):
        sheet.append(["note"])
    sheet.append(["Subgroup identifier row", "Total", "Autumn\n2021", "Spring\n2026"])
    sheet.append(["Unweighted Base", 100, 80, 90])
    sheet.append(["Weighted Base", 100.0, 81.0, 91.0])
    sheet.append(["Very concerned", 0.4, 0.42, 0.45])
    sheet.append(["Low suppressed", 0.1, "low", 0.02])
    book.save(path)


def test_parse_desnz_pat_workbook_preserves_question_metadata(tmp_path):
    path = tmp_path / "pat.xlsx"
    _workbook(path)
    rows = parse_desnz_pat_workbook(path, release_id="release", collection_run_id="run", source_url="https://example.test")
    observed = [row for row in rows if row["metadata"]["response_label"] == "Very concerned"]
    assert len(observed) == 2
    assert observed[0]["value"] == 42.0
    assert observed[0]["metadata"]["wave"] == "Autumn 2021"
    suppressed = [row for row in rows if row["metadata"]["response_label"] == "Low suppressed" and row["date"] == "2021-09-01"][0]
    assert suppressed["value"] is None
    assert suppressed["metadata"]["quality_status"] == "missing"


class _Response:
    def __init__(self, *, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Client:
    def __init__(self, responses):
        self.responses = responses

    def get(self, url, **kwargs):
        return self.responses[url]


def test_collect_desnz_pat_discovers_latest_release_and_hashes_raw_files(tmp_path):
    workbook_path = tmp_path / "source.xlsx"
    _workbook(workbook_path)
    page_path = "/government/statistics/desnz-public-attitudes-tracker-spring-2026"
    workbook_url = "https://assets.test/pat.xlsx"
    collection = {"links": {"documents": [{"title": "DESNZ Public Attitudes Tracker: Spring 2026", "base_path": page_path}]}}
    page = {"details": {"first_public_at": "2026-07-02T09:30:06+01:00", "attachments": [
        {"attachment_type": "file", "title": "DESNZ Public Attitudes Tracker: Spring 2026 - Questionnaire", "url": "https://assets.test/q.pdf"},
        {"attachment_type": "file", "title": "DESNZ Public Attitudes Tracker: Spring 2026 - Time Series", "url": workbook_url},
    ]}}
    client = _Client({DESNZ_PAT_COLLECTION_URL: _Response(payload=collection), f"https://www.gov.uk/api/content{page_path}": _Response(payload=page), workbook_url: _Response(content=workbook_path.read_bytes())})
    output = collect_desnz_pat(output=tmp_path / "bundle.json", raw_dir=tmp_path / "raw", client=client)
    bundle = json.loads(output.read_text())
    assert bundle["source"] == "desnz_pat"
    assert bundle["raw_response"]["workbook_sha256"]
    assert len(bundle["records"]) == 4
    assert bundle["provider_metadata"]["release_title"].endswith("Spring 2026")
