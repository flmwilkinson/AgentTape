"""Dump the API's OpenAPI spec to ``apps/api/openapi.json``.

Run this whenever request/response schemas change so the TS client in
``packages/shared`` regenerates with current types.

Usage:
    cd apps/api
    .venv/Scripts/python.exe scripts/export_openapi.py
"""
from __future__ import annotations

import json
from pathlib import Path

from agenttape_api.main import app

OUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUT.write_text(json.dumps(spec, indent=2, sort_keys=False), encoding="utf-8")
    print(f"wrote {OUT} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
