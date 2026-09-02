#!/usr/bin/env python3
"""Validate #168 exit-portability/reconstruction evidence structure.

This validator checks structure and release-gate conditions only. It does not
execute recovery, authenticate operators, or turn supplied evidence into a
qualification PASS.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PASS = "PASS"


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith("<")


def _refs(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_nonempty(item) for item in value)


def validate(data: dict, final: bool = False) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "thistinti-exit-portability-reconstruction-evidence":
        errors.append("schema must be thistinti-exit-portability-reconstruction-evidence")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    candidate = data.get("candidate") or {}
    if candidate.get("release_version") != "1.0.0":
        errors.append("candidate.release_version must be 1.0.0")
    if candidate.get("release_tag") != "v1.0.0":
        errors.append("candidate.release_tag must be v1.0.0")
    if data.get("qualification_result") != "NOT_A_PASS":
        errors.append("validator input cannot itself declare qualification PASS")

    if not final:
        if data.get("status") != "PREPARATION_ONLY_NOT_EXECUTED":
            errors.append("preparation status must remain PREPARATION_ONLY_NOT_EXECUTED")
        return errors

    if data.get("status") != "EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION":
        errors.append("final status must be EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION")
    if not SHA40.fullmatch(str(candidate.get("source_sha") or "")):
        errors.append("candidate.source_sha must be a full 40-hex SHA")
    if not _refs(candidate.get("release_artifact_refs")):
        errors.append("candidate.release_artifact_refs requires real references")

    package = data.get("package") or {}
    if package.get("producer_release") != "1.0.0":
        errors.append("package.producer_release must be 1.0.0")
    for key in ("format", "package_ref", "manifest_ref", "database_engine", "database_version"):
        if not _nonempty(package.get(key)):
            errors.append(f"package.{key} is required")
    if not SHA256.fullmatch(str(package.get("package_sha256") or "")):
        errors.append("package.package_sha256 must be 64 lowercase hex")
    if package.get("storage_included") is not True:
        errors.append("package.storage_included must be true for the qualified reconstruction path")

    snapshots = data.get("canonical_evidence_snapshots") or {}
    if snapshots.get("applicable") is not True:
        errors.append("canonical evidence snapshots are applicable to the post-#171 candidate")
    if not _nonempty(snapshots.get("pre_loss_identity_ref")):
        errors.append("canonical snapshot pre-loss identity reference is required")
    for key in (
        "snapshot_row_presence",
        "document_tenant_linkage",
        "canonical_byte_hash_match_after_restore",
        "reviewer_export_identity_match",
        "filesystem_fallback_not_used_as_substitute",
        "offline_inspection_method_documented",
        "offline_inspection_result",
    ):
        if snapshots.get(key) != PASS:
            errors.append(f"canonical_evidence_snapshots.{key} must be PASS")
    if not _refs(snapshots.get("evidence_refs")):
        errors.append("canonical_evidence_snapshots.evidence_refs requires real references")

    clean = data.get("clean_machine") or {}
    if not _nonempty(clean.get("environment_id")) or not _nonempty(clean.get("os_runtime")):
        errors.append("clean-machine environment and OS/runtime are required")
    if clean.get("is_source_state_absent_before_test") is not True:
        errors.append("clean target must prove original source state absent before test")
    tools = clean.get("prerequisite_tools")
    if not isinstance(tools, list) or not tools:
        errors.append("clean_machine.prerequisite_tools must identify required operator tools")
    else:
        for tool in tools:
            if not all(_nonempty(tool.get(k)) for k in ("name", "version", "purpose")):
                errors.append("each prerequisite tool requires name/version/purpose")

    reconstruction = data.get("reconstruction") or {}
    if not _nonempty(reconstruction.get("linked_recovery_evidence_ref")):
        errors.append("linked final recovery evidence is required")
    for key in (
        "package_identity_verified",
        "manifest_entry_integrity",
        "restore_on_clean_target",
        "storage_integrity",
        "canonical_evidence_integrity",
        "document_fact_finding_judgment_integrity",
        "application_read_only_smoke",
    ):
        if reconstruction.get(key) != PASS:
            errors.append(f"reconstruction.{key} must be PASS")
    elapsed = reconstruction.get("measured_elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or elapsed <= 0:
        errors.append("reconstruction.measured_elapsed_seconds must be measured and > 0")
    if not _refs(reconstruction.get("evidence_refs")):
        errors.append("reconstruction.evidence_refs requires real references")

    offline = data.get("offline_exit_inspection") or {}
    if offline.get("thistinti_service_running") is not False:
        errors.append("offline inspection must be performed without a running ThisTinti service")
    for key in (
        "container_openable",
        "manifest_json_readable",
        "integrity_metadata_inspectable",
        "source_documents_extractable",
        "database_snapshot_method_documented",
        "canonical_snapshot_records",
        "semantic_records",
        "identifier_correlation",
        "provenance_traceability",
    ):
        if offline.get(key) != PASS:
            errors.append(f"offline_exit_inspection.{key} must be PASS")
    if not _nonempty(offline.get("required_offline_method")):
        errors.append("offline_exit_inspection.required_offline_method is required")
    if not _refs(offline.get("evidence_refs")):
        errors.append("offline_exit_inspection.evidence_refs requires real references")

    compatibility = data.get("compatibility") or {}
    for key in ("forward_compatibility_claim", "backward_compatibility_claim", "database_downgrade_claim"):
        if compatibility.get(key) != "NO_UNTESTED_CLAIM":
            errors.append(f"compatibility.{key} must remain NO_UNTESTED_CLAIM")
    if compatibility.get("original_package_preserved") is not True:
        errors.append("compatibility.original_package_preserved must be true")
    if not _nonempty(compatibility.get("maintenance_eol_policy_ref")):
        errors.append("compatibility.maintenance_eol_policy_ref is required")

    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
    else:
        for finding in findings:
            if finding.get("release_blocking") is True and finding.get("status") != "CLOSED_RETESTED":
                errors.append("release-blocking findings must be CLOSED_RETESTED")

    if not _nonempty(data.get("operator_attestation_ref")):
        errors.append("real operator attestation reference is required")
    if not _refs(data.get("evidence_index")):
        errors.append("evidence_index requires real references")
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
    print("VALID_STRUCTURE_NOT_QUALIFICATION_PASS" if args.final else "VALID_PREPARATION_NOT_A_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
