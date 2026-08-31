from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_recovery_evidence", ROOT / "scripts" / "validate_recovery_evidence.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def final_evidence() -> dict:
    sha = "a" * 40
    bundle_hash = "b" * 64
    return {
        "schema": "thistinti-recovery-evidence.v0.1",
        "status": "RECOVERY_VERIFIED",
        "candidate": {"source_sha": sha, "candidate_id": "rc-final", "artifact_refs": ["artifact:installer"]},
        "environment": {
            "environment_id": "release-env",
            "deployment_model": "intended-release-model",
            "database_engine": "postgresql",
            "database_version": "recorded-version",
            "storage_model": "recorded-storage",
            "is_isolated_restore_target": True,
        },
        "objectives": {"rpo_target_seconds": 3600, "rto_target_seconds": 1800},
        "backup": {
            "procedure_ref": "log:backup-command",
            "started_at_utc": "2026-08-30T20:00:00Z",
            "completed_at_utc": "2026-08-30T20:05:00Z",
            "bundle_ref": "artifact:backup.zip",
            "bundle_sha256": bundle_hash,
            "manifest_ref": "artifact:manifest.json",
            "storage_included": True,
            "log_refs": ["log:backup"],
        },
        "restore": {
            "procedure_ref": "log:restore-command",
            "started_at_utc": "2026-08-30T20:10:00Z",
            "completed_at_utc": "2026-08-30T20:20:00Z",
            "target_ref": "env:isolated-restore",
            "used_bundle_sha256": bundle_hash,
            "log_refs": ["log:restore"],
        },
        "observed": {"recovery_point_age_seconds": 300, "recovery_time_seconds": 600},
        "verification": {
            "bundle_integrity": "PASS",
            "database_integrity": "PASS",
            "schema_migration_state": "PASS",
            "storage_integrity": "PASS",
            "tenant_workspace_isolation": "PASS",
            "document_fact_finding_judgment_integrity": "PASS",
            "application_smoke": "PASS",
            "verification_refs": ["evidence:verification"],
        },
        "findings": [],
        "operator_attestation_ref": "attestation:operator",
        "evidence_index": ["evidence:index"],
        "limitations": ["No unrecorded limitation."],
    }


def test_final_structure_accepts_complete_evidence() -> None:
    MODULE.validate(final_evidence(), final=True)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda data: data.update(status="PREPARATION_ONLY"), "final status"),
        (lambda data: data["candidate"].update(source_sha="<40-hex>"), "source_sha"),
        (lambda data: data["environment"].update(is_isolated_restore_target=False), "isolated"),
        (lambda data: data["backup"].update(storage_included=False), "storage"),
        (lambda data: data["restore"].update(used_bundle_sha256="c" * 64), "exact recorded backup"),
        (lambda data: data["verification"].update(application_smoke="NOT_EXECUTED"), "application_smoke"),
        (lambda data: data["observed"].update(recovery_time_seconds=1801), "RTO"),
    ],
)
def test_final_structure_fails_closed(mutator, message: str) -> None:
    data = final_evidence()
    mutator(data)
    with pytest.raises(ValueError, match=message):
        MODULE.validate(data, final=True)


def test_release_blocking_finding_requires_retest_pass() -> None:
    data = final_evidence()
    data["findings"] = [
        {
            "id": "REC-001",
            "severity": "HIGH",
            "state": "ACCEPTED_RISK",
            "description": "Example unresolved release blocker",
            "evidence_refs": ["evidence:finding"],
        }
    ]
    with pytest.raises(ValueError, match="RETESTED_PASS"):
        MODULE.validate(data, final=True)


def test_preparation_template_is_not_final_evidence() -> None:
    data = final_evidence()
    data["status"] = "PREPARATION_ONLY"
    MODULE.validate(data, final=False)
    with pytest.raises(ValueError):
        MODULE.validate(copy.deepcopy(data), final=True)
