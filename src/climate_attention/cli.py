"""Command line boundaries for collection, validation, serving and release work."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .config import load_config, load_country_config, load_political_config, release_config_hash, release_config_hashes
from .panel import load_account_panel, load_outlet_registry
from .pipeline import CONFIG, build_fixture, export_frontend, quality_report, release_content_hash, write_json
from .source_layers import build_layer_fixture, layer_quality_report, write_layer_parquet
from .validation import audit_configuration, audit_release
from .candidate import build_candidate, candidate_quality_report, write_candidate
from .live import (
    collect_environment_agency_floods,
    collect_firms,
    collect_gdacs,
    collect_haduk_country,
    collect_modis_ndvi,
    collect_modis_burned_area,
    load_live_countries,
)
from .economic import collect_brent, collect_desnz_fuel_prices, collect_market_prices, collect_ons_cpi


ROOT = Path(__file__).resolve().parents[2]


def validate_config() -> int:
    topics = load_config(CONFIG / "topics.uk-pilot.yaml")
    political = load_political_config(CONFIG / "political_signals.uk-pilot.yaml")
    countries = load_country_config(CONFIG / "countries.uk-pilot.yaml")
    outlets = load_outlet_registry(CONFIG / "outlet_registry.yaml")
    accounts = load_account_panel(CONFIG / "account_panel.yaml")
    print(json.dumps({"status": "pass", "topics": [topic.id for topic in topics.topics], "political_signals": len(political.signals), "outlets": len(outlets), "accounts": len(accounts), "countries": [country.id for country in countries.countries], "configuration_version": "uk-pilot-v1", "configuration_hash": release_config_hash(CONFIG), "configuration_files": release_config_hashes(CONFIG)}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uk-atlas")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-config")
    sub.add_parser("audit-panels")
    dry = sub.add_parser("dry-run"); dry.add_argument("--start", default="2026-08-01"); dry.add_argument("--end", default="2026-08-30"); dry.add_argument("--max-bytes", type=int, default=0)
    fixture = sub.add_parser("collect-fixture"); fixture.add_argument("--output", default="data/fixtures/vertical-slice.json")
    layers_fixture = sub.add_parser("collect-layers-fixture"); layers_fixture.add_argument("--output", default="data/fixtures/data-layers.json")
    aggregate = sub.add_parser("aggregate"); aggregate.add_argument("--input", default="data/fixtures/vertical-slice.json"); aggregate.add_argument("--output", default="data/processed/quality-report.json")
    quality = sub.add_parser("check-quality"); quality.add_argument("--input", default="data/fixtures/vertical-slice.json")
    layers_quality = sub.add_parser("check-layers"); layers_quality.add_argument("--input", default="data/fixtures/data-layers.json")
    parquet = sub.add_parser("export-layer-parquet"); parquet.add_argument("--input", default="data/fixtures/data-layers.json"); parquet.add_argument("--output", default="data/processed/layer_observations.parquet")
    release_audit = sub.add_parser("validate-release"); release_audit.add_argument("--input", default="data/fixtures/vertical-slice.json")
    candidate = sub.add_parser("build-live-candidate", help="assemble a physical-context candidate from live source bundles")
    candidate.add_argument("--input-dir", default="data/live")
    candidate.add_argument("--start", default="2025-01-01")
    candidate.add_argument("--end", default="2025-12-31")
    candidate.add_argument("--output", default="frontend/public/data/candidate.json")
    candidate_audit = sub.add_parser("validate-live-candidate", help="check candidate provenance and release invariants")
    candidate_audit.add_argument("--input", default="frontend/public/data/candidate.json")
    export = sub.add_parser("export-frontend"); export.add_argument("--input", default="data/fixtures/vertical-slice.json"); export.add_argument("--output", default="frontend/public/data/release.json")
    sub.add_parser("release-verify")
    sync = sub.add_parser("sync-supabase"); sync.add_argument("--input", default="data/fixtures/vertical-slice.json"); sync.add_argument("--apply-migration", action="store_true")
    sub.add_parser("collect")
    ea = sub.add_parser("collect-ea-floods-live", help="snapshot the current England Environment Agency flood feed")
    ea.add_argument("--output", default="data/live/environment_agency_alerts/bundle.json")
    ea.add_argument("--raw-dir", default="data/live/environment_agency_alerts/raw")
    gdacs = sub.add_parser("collect-gdacs-live", help="collect free GDACS major-event history")
    gdacs.add_argument("--start", required=True)
    gdacs.add_argument("--end", required=True)
    gdacs.add_argument("--output", default="data/live/gdacs/bundle.json")
    gdacs.add_argument("--cache-dir", default="data/live/gdacs/raw")
    gdacs.add_argument("--countries", default="config/countries.uk-pilot.yaml")
    haduk = sub.add_parser("collect-haduk-live", help="download and normalize one annual HadUK country temperature file")
    haduk.add_argument("--year", type=int, default=date.today().year, help="target year; defaults to the current year")
    haduk.add_argument("--output", default="data/live/haduk_grid_weather/bundle.json")
    haduk.add_argument("--raw-dir", default="data/live/haduk_grid_weather/raw")
    haduk.add_argument("--url", help="override the documented Met Office URL")
    haduk.add_argument("--input", help="use an already downloaded NetCDF file")
    modis = sub.add_parser("collect-modis-ndvi-live", help="fetch NASA MOD13C2 monthly country NDVI")
    modis.add_argument("--start", required=True)
    modis.add_argument("--end", required=True)
    modis.add_argument("--boundary-geojson", default="data/live/boundaries/ne_10m_admin_0_countries.geojson")
    modis.add_argument("--output", default="data/live/modis_mod13c2/bundle.json")
    modis.add_argument("--raw-dir", default="data/live/modis_mod13c2/raw")
    modis.add_argument("--countries", default="config/countries.uk-pilot.yaml")
    burned = sub.add_parser("collect-modis-burned-area-live", help="collect NASA MODIS MCD64 burned area via AppEEARS")
    burned.add_argument("--start", required=True)
    burned.add_argument("--end", required=True)
    burned.add_argument("--boundary-geojson", default="data/live/boundaries/ne_10m_admin_0_countries.geojson")
    burned.add_argument("--output", default="data/live/modis_burned_area/bundle.json")
    burned.add_argument("--raw-dir", default="data/live/modis_burned_area/raw")
    burned.add_argument("--countries", default="config/countries.uk-pilot.yaml")
    firms = sub.add_parser("collect-firms-live", help="collect NASA FIRMS country-day fire detections")
    firms.add_argument("--start", required=True)
    firms.add_argument("--end", required=True)
    firms.add_argument("--output", default="data/live/firms/bundle.json")
    firms.add_argument("--cache-dir", default="data/live/firms/raw")
    firms.add_argument("--boundary-geojson", default="data/live/firms/boundaries/ne_50m_admin_0_countries.geojson")
    firms.add_argument("--countries", default="config/countries.uk-pilot.yaml")
    desnz = sub.add_parser("collect-desnz-live", help="collect official weekly UK road fuel prices")
    desnz.add_argument("--output", default="data/live/desnz_fuel_prices/bundle.json")
    desnz.add_argument("--raw-dir", default="data/live/desnz_fuel_prices/raw")
    ons = sub.add_parser("collect-ons-cpi-live", help="collect official ONS CPI time series")
    ons.add_argument("--output", default="data/live/ons_cost_pressures/bundle.json")
    ons.add_argument("--raw-dir", default="data/live/ons_cost_pressures/raw")
    brent = sub.add_parser("collect-brent-live", help="collect public FRED Brent spot prices")
    brent.add_argument("--output", default="data/live/brent_oil/bundle.json")
    brent.add_argument("--raw-dir", default="data/live/brent_oil/raw")
    market = sub.add_parser("collect-market-live", help="collect exploratory daily stock closes")
    market.add_argument("--symbols", nargs="+", default=["TSLA", "BP.L", "SHEL.L"])
    market.add_argument("--start")
    market.add_argument("--end")
    market.add_argument("--output", default="data/live/market_prices/bundle.json")
    market.add_argument("--raw-dir", default="data/live/market_prices/raw")
    economics = sub.add_parser("collect-economics-live", help="collect all key public economic series")
    economics.add_argument("--symbols", nargs="+", default=["TSLA", "BP.L", "SHEL.L"])
    economics.add_argument("--start")
    economics.add_argument("--end")
    economics.add_argument("--output-dir", default="data/live")
    runs = sub.add_parser("runs"); runs.add_argument("action", choices=["inspect", "retry"])
    args = parser.parse_args(argv)
    if args.command == "validate-config": return validate_config()
    if args.command == "audit-panels":
        report = audit_configuration(CONFIG)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.command == "dry-run":
        start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
        days = (end - start).days + 1
        print(json.dumps({"status": "planned", "source": "gdelt_ngrams", "days": days, "topics": 4, "estimated_bytes_cap": args.max_bytes, "billable": False, "message": "No provider request made; use BigQuery credentials explicitly for a real capped run."}, indent=2)); return 0
    if args.command == "collect-fixture":
        path = write_json(build_fixture(), args.output); print(f"wrote {path}"); return 0
    if args.command == "collect-layers-fixture":
        path = write_json(build_layer_fixture(), args.output); print(f"wrote {path}"); return 0
    if args.command in {"aggregate", "check-quality"}:
        data = json.loads(Path(args.input).read_text())
        report = quality_report(data)
        if args.command == "aggregate": write_json(report, args.output); print(json.dumps(report, indent=2))
        else: print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.command == "validate-release":
        report = audit_release(json.loads(Path(args.input).read_text()))
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.command == "build-live-candidate":
        data = build_candidate(Path(args.input_dir), start=date.fromisoformat(args.start), end=date.fromisoformat(args.end))
        report = candidate_quality_report(data)
        if report["status"] != "pass":
            print(json.dumps(report, indent=2)); return 1
        path = write_candidate(data, Path(args.output))
        print(json.dumps({**report, "output": str(path)}, indent=2)); return 0
    if args.command == "validate-live-candidate":
        report = candidate_quality_report(json.loads(Path(args.input).read_text()))
        print(json.dumps(report, indent=2)); return 0 if report["status"] == "pass" else 1
    if args.command == "check-layers":
        report = layer_quality_report(json.loads(Path(args.input).read_text()))
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.command == "export-layer-parquet":
        output = write_layer_parquet(json.loads(Path(args.input).read_text()), args.output)
        print(f"wrote {output}")
        return 0
    if args.command == "export-frontend":
        data = json.loads(Path(args.input).read_text()); path = export_frontend(data, args.output); print(f"wrote {path}"); return 0
    if args.command == "release-verify":
        path = ROOT / "frontend/public/data/release.json"
        errors: list[str] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8")); release = data["release"]
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            print(json.dumps({"status": "fail", "errors": [f"cannot read release asset: {exc}"]}, indent=2)); return 1
        required = {"release_id", "configuration_hash", "configuration_files", "source_snapshots", "frontend_assets", "supabase_rows", "content_hash", "status"}
        errors.extend(f"missing release field: {field}" for field in sorted(required - release.keys()))
        if release.get("status") not in {"fixture", "candidate", "published", "rolled_back"}:
            errors.append("release.status is invalid")
        elif release.get("status") != "fixture":
            errors.append("the checked-in synthetic asset must remain status=fixture")
        if release.get("configuration_hash") != release_config_hash(CONFIG):
            errors.append("release configuration hash does not match the checked-in configuration")
        if release.get("configuration_files") != release_config_hashes(CONFIG):
            errors.append("release configuration file hashes do not match the checked-in configuration")
        audit = audit_release(data)
        errors.extend(audit["errors"])
        if release.get("content_hash") != release_content_hash(data):
            errors.append("release content hash is invalid")
        expected_rows = {"daily_attention": "daily_attention", "article_records": "articles", "events": "events", "physical_observations": "physical_observations", "layer_observations": "data_layers"}
        for name, collection in expected_rows.items():
            if release.get("supabase_rows", {}).get(name) != len(data.get(collection, [])):
                errors.append(f"row count mismatch for {name}")
        for relative in [*release.get("parquet_outputs", []), *release.get("frontend_assets", [])]:
            if not (ROOT / relative).exists():
                errors.append(f"declared release output is missing: {relative}")
        for relative in release.get("frontend_assets", []):
            asset = ROOT / relative
            if asset.suffix == ".json" and asset.exists():
                try:
                    asset_data = json.loads(asset.read_text(encoding="utf-8"))
                    if asset_data.get("release", {}).get("release_id") != release.get("release_id"):
                        errors.append(f"frontend asset has a different release ID: {relative}")
                    if asset_data.get("release", {}).get("content_hash") != release.get("content_hash"):
                        errors.append(f"frontend asset has a different content hash: {relative}")
                except json.JSONDecodeError:
                    errors.append(f"frontend asset is not valid JSON: {relative}")
        report = {"status": "pass" if not errors else "fail", "release_id": release.get("release_id"), "errors": errors, "audit": audit}
        print(json.dumps(report, indent=2)); return 0 if not errors else 1
    if args.command == "sync-supabase":
        data = json.loads(Path(args.input).read_text())
        payload = {
            "release_id": data["release"]["release_id"],
            "tables": data["release"]["supabase_rows"],
            "daily_attention": data.get("daily_attention", []),
            "physical_observations": data.get("physical_observations", []),
            "events": data.get("events", []),
            "layer_observations": data.get("data_layers", []),
            "source_snapshots": data.get("source_snapshots", []),
            "applied": bool(args.apply_migration),
        }
        output = write_json(payload, ROOT / "data/processed/supabase_payload.json")
        print(json.dumps({"release_id": payload["release_id"], "tables": payload["tables"], "payload": str(output), "applied": payload["applied"]}, indent=2))
        return 0
    if args.command == "collect":
        print("Real provider collection is intentionally gated on T&E-owned credentials and access approvals."); return 2
    if args.command == "collect-ea-floods-live":
        print(f"wrote {collect_environment_agency_floods(output=Path(args.output), raw_dir=Path(args.raw_dir))}"); return 0
    if args.command == "collect-gdacs-live":
        output = collect_gdacs(start=date.fromisoformat(args.start), end=date.fromisoformat(args.end), output=Path(args.output), cache_dir=Path(args.cache_dir), countries=load_live_countries(Path(args.countries)))
        print(f"wrote {output}"); return 0
    if args.command == "collect-haduk-live":
        output = collect_haduk_country(year=args.year, output=Path(args.output), raw_dir=Path(args.raw_dir), url=args.url, input_path=Path(args.input) if args.input else None)
        print(f"wrote {output}"); return 0
    if args.command == "collect-modis-ndvi-live":
        output = collect_modis_ndvi(start=date.fromisoformat(args.start), end=date.fromisoformat(args.end), output=Path(args.output), raw_dir=Path(args.raw_dir), boundary_geojson=Path(args.boundary_geojson), countries=load_live_countries(Path(args.countries)))
        print(f"wrote {output}"); return 0
    if args.command == "collect-modis-burned-area-live":
        output = collect_modis_burned_area(start=date.fromisoformat(args.start), end=date.fromisoformat(args.end), output=Path(args.output), raw_dir=Path(args.raw_dir), boundary_geojson=Path(args.boundary_geojson), countries=load_live_countries(Path(args.countries)))
        print(f"wrote {output}"); return 0
    if args.command == "collect-firms-live":
        output = collect_firms(start=date.fromisoformat(args.start), end=date.fromisoformat(args.end), output=Path(args.output), cache_dir=Path(args.cache_dir), boundary_geojson=Path(args.boundary_geojson), countries=load_live_countries(Path(args.countries)))
        print(f"wrote {output}"); return 0
    if args.command == "collect-desnz-live":
        output = collect_desnz_fuel_prices(output=Path(args.output), raw_dir=Path(args.raw_dir)); print(f"wrote {output}"); return 0
    if args.command == "collect-ons-cpi-live":
        output = collect_ons_cpi(output=Path(args.output), raw_dir=Path(args.raw_dir)); print(f"wrote {output}"); return 0
    if args.command == "collect-brent-live":
        output = collect_brent(output=Path(args.output), raw_dir=Path(args.raw_dir)); print(f"wrote {output}"); return 0
    if args.command == "collect-market-live":
        output = collect_market_prices(symbols=args.symbols, output=Path(args.output), raw_dir=Path(args.raw_dir), start=date.fromisoformat(args.start) if args.start else None, end=date.fromisoformat(args.end) if args.end else None); print(f"wrote {output}"); return 0
    if args.command == "collect-economics-live":
        output_dir = Path(args.output_dir)
        paths = [
            collect_desnz_fuel_prices(output=output_dir / "desnz_fuel_prices/bundle.json", raw_dir=output_dir / "desnz_fuel_prices/raw"),
            collect_ons_cpi(output=output_dir / "ons_cost_pressures/bundle.json", raw_dir=output_dir / "ons_cost_pressures/raw"),
            collect_brent(output=output_dir / "brent_oil/bundle.json", raw_dir=output_dir / "brent_oil/raw"),
            collect_market_prices(symbols=args.symbols, output=output_dir / "market_prices/bundle.json", raw_dir=output_dir / "market_prices/raw", start=date.fromisoformat(args.start) if args.start else None, end=date.fromisoformat(args.end) if args.end else None),
        ]
        print(json.dumps({"status": "available", "bundles": [str(path) for path in paths]}, indent=2)); return 0
    if args.command == "runs":
        print(f"run action '{args.action}' is available after a provider run manifest is created"); return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
