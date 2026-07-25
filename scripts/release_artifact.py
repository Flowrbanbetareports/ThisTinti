from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def required_release_files(version: str) -> tuple[str, ...]:
    return (
        f"ThisTinti-Setup-{version}-x64.exe",
        f"ThisTinti-Setup-{version}-x64.exe.sha256",
        f"ThisTinti-Portable-{version}-x64.zip",
        f"ThisTinti-Portable-{version}-x64.zip.sha256",
        f"ThisTinti-{version}-self-hosted-source.zip",
        f"ThisTinti-{version}-self-hosted-source.zip.sha256",
        "frozen-local-smoke.json",
        "installed-local-smoke.json",
        "installer-lifecycle-smoke.json",
        "TERMS_OF_USE.md",
        "DISCLAIMER.md",
        "PRIVACY.md",
        "TRADEMARKS.md",
        "SUPPORT.md",
        "SELF-HOSTED-RESPONSIBILITY-MATRIX.md",
        "SELF-HOSTED-ACCEPTANCE-CHECKLIST.md",
        "SBOM.cdx.json",
        "OPENAPI.json",
        "RELEASE_NOTES.md",
    )


def distributable_files(directory: Path) -> list[Path]:
    suffixes = {".exe", ".zip", ".sha256", ".json", ".md"}
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in suffixes and path.name != "release-provenance.json"
        ),
        key=lambda path: path.name,
    )


def verify_checksum_sidecar(payload: Path, sidecar: Path) -> str:
    parts = sidecar.read_text(encoding="ascii").strip().split()
    if len(parts) != 2 or parts[1] != payload.name or not SHA256_PATTERN.fullmatch(parts[0]):
        raise ValueError(f"Invalid checksum sidecar: {sidecar.name}")
    actual = sha256_file(payload)
    if parts[0] != actual:
        raise ValueError(f"Checksum mismatch for {payload.name}")
    return actual


def validate_smoke_reports(directory: Path) -> None:
    for name in ("frozen-local-smoke.json", "installed-local-smoke.json"):
        report = load_json(directory / name)
        if report.get("passed") is not True:
            raise ValueError(f"Smoke report did not pass: {name}")
    lifecycle = load_json(directory / "installer-lifecycle-smoke.json")
    required = ("baseline_installed", "upgrade_installed", "installed_smoke_passed", "uninstalled", "data_preserved")
    if lifecycle.get("passed") is not True or not all(lifecycle.get(field) is True for field in required):
        raise ValueError("Windows installer lifecycle report did not pass every required check")


def validate_source_identity(source_commit: str, source_tree: str) -> None:
    if not COMMIT_PATTERN.fullmatch(source_commit):
        raise ValueError("Source commit must be a full lowercase Git SHA")
    if not COMMIT_PATTERN.fullmatch(source_tree):
        raise ValueError("Source tree must be a full lowercase Git SHA")
