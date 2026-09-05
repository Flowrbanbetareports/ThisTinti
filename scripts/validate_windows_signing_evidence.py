from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SCHEMA_VERSION = "windows-signing-evidence.v0.2"
QUALIFICATION_CLAIM = "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1"
OFFICIAL_RELEASE_VERSION = "1.0.0"
OFFICIAL_RELEASE_TAG = "v1.0.0"
SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
PLACEHOLDER_RE = re.compile(r"^<.*>$")
REQUIRED_ROLES = {"application_exe", "installer"}


class SigningEvidenceError(ValueError):
    pass


def _require_dict(value, field):
    if not isinstance(value, dict):
        raise SigningEvidenceError(f"{field} must be an object")
    return value


def _require_list(value, field):
    if not isinstance(value, list):
        raise SigningEvidenceError(f"{field} must be an array")
    return value


def _require_text(value, field, *, final=False):
    if not isinstance(value, str) or not value.strip():
        raise SigningEvidenceError(f"{field} must be non-empty text")
    if final and PLACEHOLDER_RE.match(value.strip()):
        raise SigningEvidenceError(f"{field} contains a preparation placeholder")
    return value.strip()


def _require_sha(value, field, pattern):
    text = _require_text(value, field, final=True)
    if not pattern.fullmatch(text):
        raise SigningEvidenceError(f"{field} has invalid digest shape")
    return text.lower()


def _require_utc(value, field):
    text = _require_text(value, field, final=True)
    if not text.endswith("Z"):
        raise SigningEvidenceError(f"{field} must be UTC ISO-8601 ending in Z")
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise SigningEvidenceError(f"{field} must be valid UTC ISO-8601") from exc


def validate_manifest(data: dict, *, final: bool = False) -> None:
    data = _require_dict(data, "manifest")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SigningEvidenceError(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("qualification_claim") != QUALIFICATION_CLAIM:
        raise SigningEvidenceError("qualification_claim must bind exactly to P1/E1")

    status = data.get("status")
    if status not in {"PREPARATION_ONLY", "VERIFIED"}:
        raise SigningEvidenceError("status must be PREPARATION_ONLY or VERIFIED")
    if status == "VERIFIED" and not final:
        raise SigningEvidenceError("VERIFIED requires --final validation")
    if final and status != "VERIFIED":
        raise SigningEvidenceError("--final requires VERIFIED status")

    candidate = _require_dict(data.get("candidate"), "candidate")
    certificate = _require_dict(data.get("certificate"), "certificate")
    timestamp = _require_dict(data.get("timestamp"), "timestamp")
    artifacts = _require_list(data.get("artifacts"), "artifacts")
    if not artifacts:
        raise SigningEvidenceError("artifacts must not be empty")
    _require_dict(data.get("clean_windows_validation"), "clean_windows_validation")
    _require_dict(data.get("publication_binding"), "publication_binding")
    _require_dict(data.get("external_gate"), "external_gate")

    if not final:
        return

    source_sha = _require_sha(candidate.get("source_sha"), "candidate.source_sha", SHA40_RE)
    release_version = _require_text(candidate.get("release_version"), "candidate.release_version", final=True)
    release_tag = _require_text(candidate.get("release_tag"), "candidate.release_tag", final=True)
    if release_version != OFFICIAL_RELEASE_VERSION:
        raise SigningEvidenceError(f"candidate.release_version must be {OFFICIAL_RELEASE_VERSION}")
    if release_tag != OFFICIAL_RELEASE_TAG:
        raise SigningEvidenceError(f"candidate.release_tag must be {OFFICIAL_RELEASE_TAG}")

    _require_text(certificate.get("subject"), "certificate.subject", final=True)
    publisher_name = _require_text(certificate.get("publisher_name"), "certificate.publisher_name", final=True)
    cert_thumbprint = _require_sha(certificate.get("thumbprint_sha1"), "certificate.thumbprint_sha1", SHA40_RE)
    _require_text(certificate.get("serial_number"), "certificate.serial_number", final=True)
    not_before = _require_utc(certificate.get("not_before"), "certificate.not_before")
    not_after = _require_utc(certificate.get("not_after"), "certificate.not_after")
    if not_before >= not_after:
        raise SigningEvidenceError("certificate validity window is invalid")
    _require_text(certificate.get("ownership_ref"), "certificate.ownership_ref", final=True)

    timestamp_url = _require_text(timestamp.get("rfc3161_url"), "timestamp.rfc3161_url", final=True)
    parsed = urlparse(timestamp_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SigningEvidenceError("timestamp.rfc3161_url must be an https URL")
    _require_text(timestamp.get("policy_ref"), "timestamp.policy_ref", final=True)

    roles = []
    paths = []
    for index, artifact_value in enumerate(artifacts):
        field = f"artifacts[{index}]"
        artifact = _require_dict(artifact_value, field)
        role = _require_text(artifact.get("role"), f"{field}.role", final=True)
        path = _require_text(artifact.get("path"), f"{field}.path", final=True)
        roles.append(role)
        paths.append(path.casefold())
        if artifact.get("required") is not True:
            raise SigningEvidenceError(f"{field}.required must be true for final evidence")
        _require_sha(artifact.get("signed_sha256"), f"{field}.signed_sha256", SHA64_RE)
        if artifact.get("authenticode_status") != "Valid":
            raise SigningEvidenceError(f"{field}.authenticode_status must be Valid")
        signer = _require_sha(artifact.get("signer_thumbprint_sha1"), f"{field}.signer_thumbprint_sha1", SHA40_RE)
        if signer != cert_thumbprint:
            raise SigningEvidenceError(f"{field} signer does not match certificate thumbprint")
        if artifact.get("timestamp_present") is not True:
            raise SigningEvidenceError(f"{field}.timestamp_present must be true")
        timestamp_time = _require_utc(artifact.get("timestamp_time"), f"{field}.timestamp_time")
        if not_before > timestamp_time or timestamp_time > not_after:
            raise SigningEvidenceError(f"{field}.timestamp_time is outside certificate validity")
        _require_text(artifact.get("powershell_evidence_ref"), f"{field}.powershell_evidence_ref", final=True)
        _require_text(artifact.get("signtool_evidence_ref"), f"{field}.signtool_evidence_ref", final=True)

    if len(roles) != len(set(roles)):
        raise SigningEvidenceError("artifacts contain duplicate role")
    if len(paths) != len(set(paths)):
        raise SigningEvidenceError("artifacts contain duplicate path")
    missing_roles = REQUIRED_ROLES - set(roles)
    if missing_roles:
        raise SigningEvidenceError(f"missing required artifact roles: {', '.join(sorted(missing_roles))}")

    expected_paths = {
        "application_exe": "ThisTinti.exe",
        "installer": "ThisTinti-Setup-1.0.0-x64.exe",
    }
    for index, artifact in enumerate(artifacts):
        role = artifact["role"]
        if role in expected_paths and artifact["path"] != expected_paths[role]:
            raise SigningEvidenceError(f"artifacts[{index}].path does not match official release artifact name")

    clean = _require_dict(data.get("clean_windows_validation"), "clean_windows_validation")
    if clean.get("performed") is not True:
        raise SigningEvidenceError("clean_windows_validation.performed must be true")
    _require_text(clean.get("environment_ref"), "clean_windows_validation.environment_ref", final=True)
    publisher = _require_text(clean.get("verified_publisher"), "clean_windows_validation.verified_publisher", final=True)
    if publisher.casefold() != publisher_name.casefold():
        raise SigningEvidenceError("verified publisher does not match certificate publisher_name")
    for action in ("install_result", "uninstall_result"):
        if clean.get(action) != "PASS":
            raise SigningEvidenceError(f"clean_windows_validation.{action} must be PASS")
    _require_text(clean.get("evidence_ref"), "clean_windows_validation.evidence_ref", final=True)

    binding = _require_dict(data.get("publication_binding"), "publication_binding")
    for key in ("checksum_manifest_ref", "release_record_ref", "workflow_run_ref"):
        _require_text(binding.get(key), f"publication_binding.{key}", final=True)
    workflow_sha = _require_sha(binding.get("workflow_source_sha"), "publication_binding.workflow_source_sha", SHA40_RE)
    release_sha = _require_sha(binding.get("release_sha"), "publication_binding.release_sha", SHA40_RE)
    if workflow_sha != source_sha:
        raise SigningEvidenceError("publication binding has stale workflow SHA evidence")
    if release_sha != source_sha:
        raise SigningEvidenceError("v1.0.0 release SHA does not match final candidate source SHA")
    if binding.get("release_draft") is not False:
        raise SigningEvidenceError("publication_binding.release_draft must be false")
    if binding.get("release_prerelease") is not False:
        raise SigningEvidenceError("publication_binding.release_prerelease must be false")

    gate = _require_dict(data.get("external_gate"), "external_gate")
    for key in (
        "certificate_available",
        "signing_performed",
        "clean_windows_verified",
        "release_identity_verified",
        "final_candidate_verified",
    ):
        if gate.get(key) is not True:
            raise SigningEvidenceError(f"external_gate.{key} must be true")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Windows signing evidence manifest")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        validate_manifest(data, final=args.final)
    except (OSError, json.JSONDecodeError, SigningEvidenceError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
