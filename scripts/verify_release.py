#!/usr/bin/env python3
from __future__ import annotations

import base64
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


def validate_brand_assets() -> None:
    app_logo = (ROOT / "app/static/logo.svg").read_text(encoding="utf-8")
    site_logo = (ROOT / "site/logo.svg").read_text(encoding="utf-8")
    if app_logo != site_logo:
        raise RuntimeError("Application and public-site logos differ")
    required_logo_tokens = {
        "double-T monogram",
        "#f0b64c",
        "#55b4c3",
        "stroke-linecap=\"round\"",
    }
    missing_logo_tokens = sorted(token for token in required_logo_tokens if token not in app_logo)
    if missing_logo_tokens:
        raise RuntimeError(f"Incomplete ThisTinti identity asset: {missing_logo_tokens}")

    encoded_icon = (ROOT / "installer/assets/thistinti.ico.b64").read_text(encoding="utf-8").strip()
    try:
        icon = base64.b64decode(encoded_icon, validate=True)
    except ValueError as exc:
        raise RuntimeError("Invalid Base64 Windows icon source") from exc
    if len(icon) < 4096 or not icon.startswith(b"\x00\x00\x01\x00"):
        raise RuntimeError("Generated Windows icon source is not a valid ICO payload")

    app_css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
    site_css = (ROOT / "site/styles.css").read_text(encoding="utf-8")
    site_js = (ROOT / "site/site.js").read_text(encoding="utf-8")
    site_html = (ROOT / "site/index.html").read_text(encoding="utf-8")
    for name, stylesheet in (("application", app_css), ("public site", site_css)):
        if "prefers-reduced-motion" not in stylesheet:
            raise RuntimeError(f"{name} motion does not respect reduced-motion preferences")
    if "IntersectionObserver" not in site_js or "hero-mark" not in site_html:
        raise RuntimeError("Public-site progressive motion or new identity entry point is missing")


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
    validate_brand_assets()
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
