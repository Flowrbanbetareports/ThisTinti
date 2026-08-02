from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DISTRIBUTION_IDENTITY_NAME = "BUILD-IDENTITY.json"


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
        "installed-diagnostics-report.json",
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
        "VERIFY-THIS-DOWNLOAD.md",
    )


def publication_manifest_files(provenance: dict, version: str) -> dict[str, dict]:
    manifest_files = provenance.get("files")
    if not isinstance(manifest_files, list) or not manifest_files:
        raise ValueError("Artifact provenance has no file manifest")
    manifest_by_name = {
        str(item.get("name")): item
        for item in manifest_files
        if isinstance(item, dict) and item.get("name")
    }
    if not set(required_release_files(version)).issubset(manifest_by_name):
        raise ValueError("Artifact provenance omits required release files")
    return manifest_by_name


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
    diagnostics = load_json(directory / "installed-diagnostics-report.json")
    if diagnostics.get("schema") != "thistinti.windows-installed-diagnostics.v1":
        raise ValueError("Windows installed diagnostics report has an unsupported schema")
    required_diagnostics = (
        "api_mocked",
        "read_only_outcome",
        "active_outcome",
        "numeric_rejection",
        "restart_persistence",
    )
    if (
        diagnostics.get("passed") is not True
        or diagnostics.get("api_mocked") is not False
        or diagnostics.get("read_only_outcome") != "PARZIALE"
        or diagnostics.get("active_outcome") != "PASS"
        or diagnostics.get("numeric_rejection") != "PASS"
        or diagnostics.get("restart_persistence") is not True
        or not all(field in diagnostics for field in required_diagnostics)
    ):
        raise ValueError("Windows installed diagnostics report did not pass every required check")
    lifecycle = load_json(directory / "installer-lifecycle-smoke.json")
    required = (
        "baseline_installed",
        "upgrade_installed",
        "installed_smoke_passed",
        "installed_diagnostics_passed",
        "uninstalled",
        "data_preserved",
    )
    if lifecycle.get("passed") is not True or not all(lifecycle.get(field) is True for field in required):
        raise ValueError("Windows installer lifecycle report did not pass every required check")


def validate_source_identity(source_commit: str, source_tree: str) -> None:
    if not COMMIT_PATTERN.fullmatch(source_commit):
        raise ValueError("Source commit must be a full lowercase Git SHA")
    if not COMMIT_PATTERN.fullmatch(source_tree):
        raise ValueError("Source tree must be a full lowercase Git SHA")


def build_distribution_identity(
    *,
    version: str,
    source_commit: str,
    source_tree: str,
    workflow_run: int,
    workflow_run_number: int,
    artifact_name: str,
) -> dict[str, Any]:
    validate_source_identity(source_commit, source_tree)
    if workflow_run < 1 or workflow_run_number < 1:
        raise ValueError("Distribution identity requires positive workflow run identifiers")
    if not artifact_name.startswith("ThisTinti-Windows-"):
        raise ValueError("Distribution identity artifact name is invalid")
    return {
        "schema": "thistinti.distribution-identity.v1",
        "version": version,
        "source": {"commit": source_commit, "tree": source_tree},
        "build": {
            "workflow": "Build Windows Free Download",
            "run_id": workflow_run,
            "run_number": workflow_run_number,
            "artifact_name": artifact_name,
        },
        "verification": {
            "detached_checksum_required": True,
            "provenance_manifest_required": True,
        },
    }


def validate_portable_identity(
    portable: Path,
    *,
    expected_version: str,
    expected_commit: str,
    expected_tree: str,
    expected_workflow_run: int | None = None,
    expected_workflow_run_number: int | None = None,
    expected_artifact_name: str | None = None,
) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(portable) as archive:
            matches = [info for info in archive.infolist() if info.filename == DISTRIBUTION_IDENTITY_NAME]
            if len(matches) != 1:
                raise ValueError("Portable archive must contain exactly one root BUILD-IDENTITY.json")
            identity = json.loads(archive.read(matches[0]).decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read portable distribution identity: {exc}") from exc
    if not isinstance(identity, dict) or identity.get("schema") != "thistinti.distribution-identity.v1":
        raise ValueError("Unsupported or missing portable distribution identity")
    if identity.get("version") != expected_version:
        raise ValueError("Portable distribution version does not match")
    source = identity.get("source") if isinstance(identity.get("source"), dict) else {}
    if source.get("commit") != expected_commit or source.get("tree") != expected_tree:
        raise ValueError("Portable distribution source identity does not match")
    build = identity.get("build") if isinstance(identity.get("build"), dict) else {}
    expected = {
        "run_id": expected_workflow_run,
        "run_number": expected_workflow_run_number,
        "artifact_name": expected_artifact_name,
    }
    for field, value in expected.items():
        if value is not None and build.get(field) != value:
            raise ValueError(f"Portable distribution build {field} does not match")
    verification = identity.get("verification") if isinstance(identity.get("verification"), dict) else {}
    if not all(
        verification.get(field) is True for field in ("detached_checksum_required", "provenance_manifest_required")
    ):
        raise ValueError("Portable distribution identity omits detached verification requirements")
    return identity
