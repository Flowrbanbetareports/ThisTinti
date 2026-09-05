#!/usr/bin/env python3
"""Validate RELEASE 1.0.0 data-protection qualification evidence structure.

This validates structure and fail-closed release conditions only. It does not
authenticate reviewers, prove host controls, or turn supplied evidence into a
qualification PASS.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SURFACES = {
    "originals",
    "database",
    "canonical_evidence_snapshots",
    "quarantine",
    "logs",
    "temp",
    "exports",
    "backups",
    "diagnostics_or_crash_material",
}
REQUIRED_ACTIONS = {"startup", "ingestion_analysis", "restart"}


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _rfc3339(value: object) -> bool:
    if not _nonempty(value):
        return False
    text = str(value)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return text.endswith("Z") or "+00:00" in text


def validate(data: dict, final: bool = False) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "thistinti-data-protection-evidence":
        errors.append("schema must be thistinti-data-protection-evidence")
    if data.get("schema_version") != 2:
        errors.append("schema_version must be 2")

    candidate = data.get("candidate") or {}
    if candidate.get("release_version") != "1.0.0":
        errors.append("candidate.release_version must be 1.0.0")
    if candidate.get("release_tag") != "v1.0.0":
        errors.append("candidate.release_tag must be v1.0.0")

    if not final:
        if data.get("qualification_decision") != "NOT_A_PASS":
            errors.append("preparation manifest must remain NOT_A_PASS")
        return errors

    if data.get("status") != "EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION":
        errors.append("final status must be EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION")
    if not SHA40.fullmatch(str(candidate.get("source_sha") or "")):
        errors.append("candidate.source_sha must be a full 40-hex SHA")
    if not _nonempty(candidate.get("windows_artifact")):
        errors.append("candidate.windows_artifact is required")
    if not SHA256.fullmatch(str(candidate.get("windows_artifact_sha256") or "")):
        errors.append("candidate.windows_artifact_sha256 must be 64 lowercase hex")
    if not _nonempty(candidate.get("self_hosted_artifact")):
        errors.append("candidate.self_hosted_artifact is required")
    if not _nonempty(candidate.get("self_hosted_digest")):
        errors.append("candidate.self_hosted_digest is required")

    local = data.get("local_edition") or {}
    if local.get("application_level_encryption_at_rest_claim") is not False:
        errors.append("1.0.0 posture must not claim application-level encryption at rest")
    for key in (
        "host_encryption_prerequisite_or_recommendation_verified",
        "storage_surfaces_verified",
        "canonical_evidence_snapshot_storage_verified",
        "uninstall_retention_behavior_verified",
        "complete_deletion_procedure_verified",
    ):
        if local.get(key) is not True:
            errors.append(f"local_edition.{key} must be true")

    hosted = data.get("self_hosted") or {}
    for key in (
        "reference_environment_identified",
        "database_storage_encryption_documented",
        "document_storage_encryption_documented",
        "canonical_evidence_snapshot_storage_documented",
        "backup_encryption_documented",
        "key_ownership_and_recovery_documented",
        "transport_boundary_documented",
        "operator_responsibility_boundary_documented",
    ):
        if hosted.get(key) is not True:
            errors.append(f"self_hosted.{key} must be true")

    outbound = data.get("outbound_network") or {}
    if outbound.get("observation_executed") is not True:
        errors.append("outbound_network.observation_executed must be true")
    if not _nonempty(outbound.get("evidence_reference")):
        errors.append("outbound_network.evidence_reference is required")
    if outbound.get("unexplained_destinations") != []:
        errors.append("outbound_network.unexplained_destinations must be empty")
    if outbound.get("silent_document_or_evidence_upload_detected") is not False:
        errors.append("silent document/evidence upload must be explicitly false")
    ctx = outbound.get("observation_context") or {}
    for key in ("windows_version", "tool_name", "tool_version"):
        if not _nonempty(ctx.get(key)):
            errors.append(f"outbound_network.observation_context.{key} is required")
    for key in ("started_at_utc", "ended_at_utc"):
        if not _rfc3339(ctx.get(key)):
            errors.append(f"outbound_network.observation_context.{key} must be UTC RFC3339")
    actions = ctx.get("actions_exercised")
    if not isinstance(actions, list) or not REQUIRED_ACTIONS.issubset(set(actions)):
        errors.append("outbound observation must exercise startup, ingestion_analysis and restart")

    surfaces = data.get("sensitive_surface_review") or {}
    if set(surfaces) != SURFACES:
        errors.append("sensitive_surface_review must contain exactly the required surfaces")
    else:
        for name, status in surfaces.items():
            if status != "PASS":
                errors.append(f"sensitive_surface_review.{name} must be PASS")

    review = data.get("independent_review") or {}
    if review.get("security_issue") != 134 or not _nonempty(review.get("security_review_reference")):
        errors.append("independent security review #134 reference is required")
    if review.get("privacy_legal_claims_issue") != 135 or not _nonempty(review.get("privacy_legal_claims_review_reference")):
        errors.append("independent privacy/legal/claims review #135 reference is required")
    if review.get("release_blocking_findings_open") is not False:
        errors.append("release_blocking_findings_open must be explicitly false")

    if data.get("qualification_decision") != "NOT_A_PASS":
        errors.append("validator output cannot itself declare qualification PASS")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    errors = validate(data, final=args.final)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1
    result = "VALID_STRUCTURE_NOT_QUALIFICATION_PASS" if args.final else "VALID_PREPARATION_NOT_A_PASS"
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
