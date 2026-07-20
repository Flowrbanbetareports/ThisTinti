#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.version import RELEASE_VERSION  # noqa: E402

SECRET_PATTERN = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")
TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".toml",
    ".ini",
    ".yml",
    ".yaml",
    ".json",
    ".sql",
    ".example",
}
SKIP_DIRS = {
    ".git",
    ".venv",
    ".venv-verify",
    ".venv-runtime-lock",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".runtime",
}


def scan_sources() -> None:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            "Dockerfile",
            "Makefile",
            ".replit",
            ".dockerignore",
            ".gitignore",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SECRET_PATTERN.search(text):
            findings.append(f"Potential OpenAI key in {path.relative_to(ROOT)}")
    frontend = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    if "localStorage" in frontend or "sessionStorage" in frontend:
        findings.append("Browser token storage is present")
    if re.search(r"\sstyle\s*=", html, flags=re.IGNORECASE):
        findings.append("Inline style attribute conflicts with CSP")
    if findings:
        raise RuntimeError("\n".join(findings))


def validate_openapi() -> None:
    schema = json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))
    if schema.get("info", {}).get("title") != "ThisTinti" or schema.get("info", {}).get("version") != RELEASE_VERSION:
        raise RuntimeError("OpenAPI metadata mismatch")
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            responses = operation.get("responses", {})
            success = next((responses[code] for code in ("200", "201", "202", "204") if code in responses), None)
            if success is None:
                raise RuntimeError(f"OpenAPI operation has no success response: {method.upper()} {path}")
            for media_type, media in success.get("content", {}).items():
                if media_type == "application/json" and not media.get("schema"):
                    raise RuntimeError(f"OpenAPI JSON response has no schema: {method.upper()} {path}")


def internal_checks() -> int:
    validate_openapi()
    scan_sources()
    return 0


def main() -> int:
    if sys.argv[1:] == ["--internal-checks"]:
        return internal_checks()
    script = ROOT / "scripts" / "verify_release.sh"
    os.execve("/bin/bash", ["bash", str(script)], os.environ.copy())  # nosec B606
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
