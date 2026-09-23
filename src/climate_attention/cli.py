"""Command line boundaries for collection, validation, serving and release work."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .config import config_hash, load_config, load_political_config
from .panel import load_account_panel, load_outlet_registry
from .pipeline import CONFIG, build_fixture, export_frontend, quality_report, write_json


ROOT = Path(__file__).resolve().parents[2]


def validate_config() -> int:
    topics = load_config(CONFIG / "topics.uk-pilot.yaml")
    political = load_political_config(CONFIG / "political_signals.uk-pilot.yaml")
    outlets = load_outlet_registry(CONFIG / "outlet_registry.yaml")
    accounts = load_account_panel(CONFIG / "account_panel.yaml")
    print(json.dumps({"status": "pass", "topics": [topic.id for topic in topics.topics], "political_signals": len(political.signals), "outlets": len(outlets), "accounts": len(accounts), "configuration_version": "uk-pilot-v1", "topic_config_hash": config_hash(CONFIG / "topics.uk-pilot.yaml")}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uk-atlas")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-config")
    dry = sub.add_parser("dry-run"); dry.add_argument("--start", default="2026-08-01"); dry.add_argument("--end", default="2026-08-30"); dry.add_argument("--max-bytes", type=int, default=0)
    fixture = sub.add_parser("collect-fixture"); fixture.add_argument("--output", default="data/fixtures/vertical-slice.json")
    aggregate = sub.add_parser("aggregate"); aggregate.add_argument("--input", default="data/fixtures/vertical-slice.json"); aggregate.add_argument("--output", default="data/processed/quality-report.json")
    quality = sub.add_parser("check-quality"); quality.add_argument("--input", default="data/fixtures/vertical-slice.json")
    export = sub.add_parser("export-frontend"); export.add_argument("--input", default="data/fixtures/vertical-slice.json"); export.add_argument("--output", default="frontend/public/data/release.json")
    sub.add_parser("release-verify")
    sync = sub.add_parser("sync-supabase"); sync.add_argument("--input", default="data/fixtures/vertical-slice.json"); sync.add_argument("--apply-migration", action="store_true")
    sub.add_parser("collect")
    runs = sub.add_parser("runs"); runs.add_argument("action", choices=["inspect", "retry"])
    args = parser.parse_args(argv)
    if args.command == "validate-config": return validate_config()
    if args.command == "dry-run":
        start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
        days = (end - start).days + 1
        print(json.dumps({"status": "planned", "source": "gdelt_ngrams", "days": days, "topics": 4, "estimated_bytes_cap": args.max_bytes, "billable": False, "message": "No provider request made; use BigQuery credentials explicitly for a real capped run."}, indent=2)); return 0
    if args.command == "collect-fixture":
        path = write_json(build_fixture(), args.output); print(f"wrote {path}"); return 0
    if args.command in {"aggregate", "check-quality"}:
        data = json.loads(Path(args.input).read_text())
        report = quality_report(data)
        if args.command == "aggregate": write_json(report, args.output); print(json.dumps(report, indent=2))
        else: print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.command == "export-frontend":
        data = json.loads(Path(args.input).read_text()); path = export_frontend(data, args.output); print(f"wrote {path}"); return 0
    if args.command == "release-verify":
        path = ROOT / "frontend/public/data/release.json"
        data = json.loads(path.read_text()); release = data["release"]
        required = {"release_id", "configuration_hash", "source_snapshots", "frontend_assets"}
        missing = sorted(required - release.keys()); print(json.dumps({"status": "pass" if not missing else "fail", "release_id": release.get("release_id"), "missing": missing}, indent=2)); return 0 if not missing else 1
    if args.command == "sync-supabase":
        data = json.loads(Path(args.input).read_text())
        payload = {
            "release_id": data["release"]["release_id"],
            "tables": data["release"]["supabase_rows"],
            "daily_attention": data.get("daily_attention", []),
            "physical_observations": data.get("physical_observations", []),
            "events": data.get("events", []),
            "applied": bool(args.apply_migration),
        }
        output = write_json(payload, ROOT / "data/processed/supabase_payload.json")
        print(json.dumps({"release_id": payload["release_id"], "tables": payload["tables"], "payload": str(output), "applied": payload["applied"]}, indent=2))
        return 0
    if args.command == "collect":
        print("Real provider collection is intentionally gated on T&E-owned credentials and access approvals."); return 2
    if args.command == "runs":
        print(f"run action '{args.action}' is available after a provider run manifest is created"); return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
