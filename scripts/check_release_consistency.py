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

from app.version import PYTHON_PACKAGE_VERSION, RELEASE_VERSION  # noqa: E402
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


def has_public_preview_line(text: str, version: str) -> bool:
    return any(version in line and "Public Preview" in line for line in text.splitlines())


def validate_publication_document_state(failures: list[str]) -> None:
    publication = load_json(ROOT / "builds" / "publication-latest.json")
    version = str(publication.get("version") or "")
    if not version:
        failures.append("Latest publication evidence has no version")
        return

    # These public-facing documents must always identify the latest immutable
    # publication on the same line as its Public Preview status. This remains
    # valid when development later moves to a newer internal candidate.
    for relative in ("README.md", "ROADMAP.md", "docs/BETA_READINESS_STATUS.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        if not has_public_preview_line(text, version):
            failures.append(f"{relative} does not identify published {version} as a Public Preview")

    release_notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    section_match = re.search(
        rf"(?ms)^# {re.escape(version)}\b.*?(?=^# |\Z)",
        release_notes,
    )
    if section_match is None or "Public Preview" not in section_match.group(0):
        failures.append(f"RELEASE_NOTES.md does not record {version} as a published Public Preview")

    # When the current source version is exactly the published version, the
    # operational documents must not still call it an unpublished candidate.
    if version == RELEASE_VERSION:
        for relative in ("docs/OPERATIONS.md", "docs/PRODUCTION_READINESS.md", "docs/THREAT_MODEL.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            if not has_public_preview_line(text, version):
                failures.append(f"{relative} still does not identify current {version} as Public Preview")
            if "candidata interna non pubblicata" in text:
                failures.append(f"{relative} still describes published {version} as unpublished")


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

    package_version = pyproject.get("project", {}).get("version")
    if package_version != PYTHON_PACKAGE_VERSION:
        failures.append(
            f"pyproject.toml version is {package_version!r}; expected PEP 440 equivalent {PYTHON_PACKAGE_VERSION!r}"
        )

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
    validate_publication_document_state(failures)
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
