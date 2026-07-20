from __future__ import annotations

import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
URL = re.compile(r"https?://[^\s\"']+")


def test_runtime_contains_no_nonlocal_http_endpoints():
    found: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        for value in URL.findall(path.read_text(encoding="utf-8")):
            if not value.startswith(("http://127.0.0.1", "http://localhost")):
                found.append(f"{path.relative_to(APP_ROOT)}: {value}")
    assert found == []
