#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.version import RELEASE_VERSION  # noqa: E402

VERSION = RELEASE_VERSION
OUTPUT = ROOT.parent / f"ThisTinti-{VERSION}.zip"
CHECKSUM = ROOT.parent / f"ThisTinti-{VERSION}.sha256"

EXCLUDED_DIRS = {
    ".git",
    ".github-cache",
    ".pytest_cache",
    ".ruff_cache",
    ".browser-smoke",
    ".live-smoke",
    ".openapi-storage",
    ".smoke",
    ".venv",
    ".venv-verify",
    ".venv-runtime-lock",
    "__pycache__",
    ".runtime",
    "data",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".db-shm", ".db-wal"}
EXCLUDED_FILES = {".coverage", ".env"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if relative.parts[:2] == ("deploy", "enterprise"):
        if relative.name in {".env", "operator-acceptance.json"}:
            return False
        if len(relative.parts) >= 3 and relative.parts[2] in {"secrets", "backups", "logs"}:
            return relative.name == ".gitkeep"
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_FILES:
        return False
    if any(path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return False
    return path.is_file()


def zip_info(relative: Path, executable: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(str(Path("ThisTinti") / relative).replace(os.sep, "/"))
    info.date_time = (2026, 7, 20, 0, 0, 0)
    mode = 0o755 if executable else 0o644
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def main() -> int:
    files = sorted(path for path in ROOT.rglob("*") if should_include(path))
    if not files:
        print("No files found", file=sys.stderr)
        return 1
    OUTPUT.unlink(missing_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT)
            executable = os.access(path, os.X_OK) and path.suffix in {".py", ".sh"}
            archive.writestr(zip_info(relative, executable), path.read_bytes())
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    CHECKSUM.write_text(f"{digest}  {OUTPUT.name}\n", encoding="utf-8")
    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad:
            print(f"Corrupted ZIP member: {bad}", file=sys.stderr)
            return 1
    print(f"Created {OUTPUT}")
    print(f"SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
