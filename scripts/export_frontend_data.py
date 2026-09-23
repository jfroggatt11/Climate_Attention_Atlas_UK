"""Export a validated release fixture for the browser.

The production boundary is intentionally explicit: this script reads prepared
data and writes a release asset. It never collects a source or runs a refresh.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from climate_attention.pipeline import export_frontend


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/fixtures/vertical-slice.json")
    parser.add_argument("--output", default="frontend/public/data/release.json")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    export_frontend(data, args.output)
    print(f"exported {args.output} with release {data['release']['release_id']}")


if __name__ == "__main__":
    main()
