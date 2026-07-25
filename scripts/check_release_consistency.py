#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.version import RELEASE_VERSION  # noqa: E402
from scripts.generate_openapi import render_openapi  # noqa: E402
from scripts.generate_sbom import render_sbom  # noqa: E402

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def read_installer_version(text: str) -> str | None:
    match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', text)
    return match.group(1) if match else None


def validate_generated_file(path: Path, expected: str, failures: list[str]) -> None:
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        failures.append(f"{path.relative_to(ROOT)} is stale; regenerate release metadata")


def validate_release_records(failures: list[str]) -> None:
    release = load_json(ROOT / "builds" / "release-latest.json")
    publication = load_json(ROOT / "builds" / "publication-latest.json")
    if release.get("version") != publication.get("version"):
        failures.append("Latest release and publication evidence refer to different versions")
    if release.get("tag") != publication.get("tag"):
        failures.append("Latest release and publication evidence refer to different tags")
    if release.get("release_commit") != publication.get("release_commit"):
        failures.append("Latest release and publication evidence refer to different commits")
    if not COMMIT_PATTERN.fullmatch(str(release.get("release_commit") or "")):
        failures.append("Latest release evidence has no full release commit")

    verification = release.get("verification")
    if not isinstance(verification, dict):
        failures.append("Latest release verification is missing")
        return
    for field in ("installer_sha256", "portable_sha256", "self_hosted_source_sha256"):
        if not SHA256_PATTERN.fullmatch(str(verification.get(field) or "")):
            failures.append(f"Latest release verification has invalid {field}")


def validate_windows_baseline(failures: list[str]) -> None:
    baseline = load_json(ROOT / "builds" / "windows-upgrade-baseline.json")
    required = {
        "schema": "thistinti.windows-upgrade-baseline.v1",
        "tag": f"v{baseline.get('version')}",
        "installer": f"ThisTinti-Setup-{baseline.get('version')}-x64.exe",
    }
    for field, expected in required.items():
        if baseline.get(field) != expected:
            failures.append(f"Windows upgrade baseline {field} must be {expected!r}")
    if not SHA256_PATTERN.fullmatch(str(baseline.get("sha256") or "")):
        failures.append("Windows upgrade baseline has no valid SHA-256")
    if not COMMIT_PATTERN.fullmatch(str(baseline.get("release_commit") or "")):
        failures.append("Windows upgrade baseline has no full release commit")


def validate_version_sources(failures: list[str]) -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    installer_version = read_installer_version(
        (ROOT / "installer" / "windows" / "ThisTinti.iss").read_text(encoding="utf-8")
    )
    versions = {
        "app/version.py": RELEASE_VERSION,
        "pyproject.toml": pyproject.get("project", {}).get("version"),
        "installer/windows/ThisTinti.iss": installer_version,
        "docs/openapi.json": load_json(ROOT / "docs" / "openapi.json").get("info", {}).get("version"),
        "docs/sbom.cdx.json": (
            load_json(ROOT / "docs" / "sbom.cdx.json").get("metadata", {}).get("component", {}).get("version")
        ),
        "docs/evidence/beta/external-gates.json": load_json(
            ROOT / "docs" / "evidence" / "beta" / "external-gates.json"
        ).get("candidate_version"),
    }
    for source, version in versions.items():
        if version != RELEASE_VERSION:
            failures.append(f"{source} version is {version!r}; expected {RELEASE_VERSION!r}")

    for relative in ("README.md", "RELEASE_NOTES.md", "docs/BETA_READINESS_STATUS.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        if RELEASE_VERSION not in text:
            failures.append(f"{relative} does not identify candidate {RELEASE_VERSION}")

    sbom = load_json(ROOT / "docs" / "sbom.cdx.json")
    expected_ref = f"pkg:generic/thistinti@{RELEASE_VERSION}"
    component = sbom.get("metadata", {}).get("component", {})
    if component.get("bom-ref") != expected_ref:
        failures.append("SBOM application reference does not match the release version")
    dependencies = sbom.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies or dependencies[0].get("ref") != expected_ref:
        failures.append("SBOM dependency root does not match the release version")


def validate_release_consistency() -> list[str]:
    failures: list[str] = []
    validate_version_sources(failures)
    validate_generated_file(ROOT / "docs" / "openapi.json", render_openapi(), failures)
    validate_generated_file(ROOT / "docs" / "sbom.cdx.json", render_sbom(), failures)
    validate_release_records(failures)
    validate_windows_baseline(failures)
    return failures


def main() -> int:
    try:
        failures = validate_release_consistency()
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"Release consistency check failed: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("Release consistency check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Release metadata is reproducible and consistent for {RELEASE_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
