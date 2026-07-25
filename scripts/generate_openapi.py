#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("THISTINTI_DATABASE_URL", f"sqlite:///{ROOT / '.openapi.db'}")
os.environ.setdefault("THISTINTI_STORAGE_DIR", str(ROOT / ".openapi-storage"))
os.environ.setdefault("THISTINTI_SECRET_KEY", "openapi-generation-secret-with-more-than-32-characters")
os.environ.setdefault("THISTINTI_AUTO_CREATE_SCHEMA", "false")

from app.main import app  # noqa: E402


def render_openapi() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the committed ThisTinti OpenAPI contract.")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "openapi.json")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_openapi(), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
