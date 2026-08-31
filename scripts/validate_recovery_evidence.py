#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
VERIFY_KEYS = (
    "bundle_integrity",
    "database_integrity",
    "schema_migration_state",
    "storage_integrity",
    "tenant_workspace_isolation",
    "document_fact_finding_judgment_integrity",
    "application_smoke",
)


def fail(message: str) -> None:
    raise ValueError(message)


def require_dict(value, name: str):
    if not isinstance(value, dict):
        fail(f"{name} must be an object")
    return value


def require_text(value, name: str, *, final: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{name} must be a non-empty string")
    value = value.strip()
    if final and value.startswith("<") and value.endswith(">"):
        fail(f"{name} still contains a placeholder")
    return value


def require_refs(value, name: str, *, final: bool = False) -> list[str]:
    if not isinstance(value, list):
        fail(f"{name} must be an array")
    refs = [require_text(item, f"{name}[]", final=final) for item in value]
    if final and not refs:
        fail(f"{name} must contain evidence")
    if len(refs) != len(set(refs)):
        fail(f"{name} contains duplicate references")
    return refs


def validate(data: dict, *, final: bool = False) -> None:
    if data.get("schema") != "thistinti-recovery-evidence.v0.1":
        fail("unsupported schema")
    status = require_text(data.get("status"), "status", final=final)
    if final and status != "RECOVERY_VERIFIED":
        fail("final status must be RECOVERY_VERIFIED")

    candidate = require_dict(data.get("candidate"), "candidate")
    source_sha = require_text(candidate.get("source_sha"), "candidate.source_sha", final=final)
    if final and not SHA40.fullmatch(source_sha):
        fail("candidate.source_sha must be lowercase 40-hex")
    require_text(candidate.get("candidate_id"), "candidate.candidate_id", final=final)
    require_refs(candidate.get("artifact_refs"), "candidate.artifact_refs", final=final)

    env = require_dict(data.get("environment"), "environment")
    for key in ("environment_id", "deployment_model", "database_engine", "database_version", "storage_model"):
        require_text(env.get(key), f"environment.{key}", final=final)
    if final and env.get("is_isolated_restore_target") is not True:
        fail("final restore target must be explicitly isolated")

    objectives = require_dict(data.get("objectives"), "objectives")
    observed = require_dict(data.get("observed"), "observed")
    for key in ("rpo_target_seconds", "rto_target_seconds"):
        value = objectives.get(key)
        if final and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            fail(f"objectives.{key} must be a positive integer")
    for key in ("recovery_point_age_seconds", "recovery_time_seconds"):
        value = observed.get(key)
        if final and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            fail(f"observed.{key} must be a non-negative integer")
    if final and observed["recovery_point_age_seconds"] > objectives["rpo_target_seconds"]:
        fail("observed recovery point age exceeds RPO target")
    if final and observed["recovery_time_seconds"] > objectives["rto_target_seconds"]:
        fail("observed recovery time exceeds RTO target")

    backup = require_dict(data.get("backup"), "backup")
    restore = require_dict(data.get("restore"), "restore")
    for section_name, section in (("backup", backup), ("restore", restore)):
        require_text(section.get("procedure_ref"), f"{section_name}.procedure_ref", final=final)
        require_text(section.get("started_at_utc"), f"{section_name}.started_at_utc", final=final)
        require_text(section.get("completed_at_utc"), f"{section_name}.completed_at_utc", final=final)
        require_refs(section.get("log_refs"), f"{section_name}.log_refs", final=final)
    require_text(backup.get("bundle_ref"), "backup.bundle_ref", final=final)
    require_text(backup.get("manifest_ref"), "backup.manifest_ref", final=final)
    backup_hash = require_text(backup.get("bundle_sha256"), "backup.bundle_sha256", final=final)
    restore_hash = require_text(restore.get("used_bundle_sha256"), "restore.used_bundle_sha256", final=final)
    require_text(restore.get("target_ref"), "restore.target_ref", final=final)
    if final:
        if backup.get("storage_included") is not True:
            fail("final recovery evidence must include application storage")
        if not SHA256.fullmatch(backup_hash) or not SHA256.fullmatch(restore_hash):
            fail("backup and restore hashes must be lowercase 64-hex")
        if backup_hash != restore_hash:
            fail("restore must use the exact recorded backup bundle")

    verification = require_dict(data.get("verification"), "verification")
    for key in VERIFY_KEYS:
        value = require_text(verification.get(key), f"verification.{key}", final=final)
        if final and value != "PASS":
            fail(f"verification.{key} must be PASS")
    require_refs(verification.get("verification_refs"), "verification.verification_refs", final=final)

    findings = data.get("findings")
    if not isinstance(findings, list):
        fail("findings must be an array")
    for index, finding in enumerate(findings):
        finding = require_dict(finding, f"findings[{index}]")
        severity = require_text(finding.get("severity"), f"findings[{index}].severity", final=final).upper()
        state = require_text(finding.get("state"), f"findings[{index}].state", final=final).upper()
        require_text(finding.get("id"), f"findings[{index}].id", final=final)
        require_text(finding.get("description"), f"findings[{index}].description", final=final)
        require_refs(finding.get("evidence_refs"), f"findings[{index}].evidence_refs", final=final)
        if final and state in {"OPEN", "FIXED_PENDING_RETEST"}:
            fail("final evidence contains unresolved finding")
        if final and severity in {"BLOCKER", "CRITICAL", "HIGH", "SERIOUS"} and state != "RETESTED_PASS":
            fail("release-blocking finding lacks RETESTED_PASS")

    require_text(data.get("operator_attestation_ref"), "operator_attestation_ref", final=final)
    require_refs(data.get("evidence_index"), "evidence_index", final=final)
    require_refs(data.get("limitations"), "limitations")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ThisTinti recovery evidence")
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            fail("evidence root must be an object")
        validate(payload, final=args.final)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"RECOVERY EVIDENCE INVALID: {exc}")
        return 1
    print("RECOVERY EVIDENCE VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
