from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "validate_performance_capacity_evidence.py"
SPEC = importlib.util.spec_from_file_location("validate_performance_capacity", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate = MODULE.validate


def _run(size: str, n: int) -> dict:
    return {
        "workload_size": size,
        "run_id": f"{size}-{n}",
        "started_at_utc": f"2026-09-02T10:0{n}:00Z",
        "ended_at_utc": f"2026-09-02T10:1{n}:00Z",
        "elapsed_seconds": 60.0 + n,
        "throughput_practices_per_second": 1.5,
        "peak_ram_bytes": 900_000_000,
        "peak_cpu_percent": 75.0,
        "latency_seconds": {"median": 0.8, "p95": 1.4},
        "evidence_refs": [f"evidence:{size}-{n}"],
    }


def final_manifest() -> dict:
    runs = [_run(size, n) for size in ("small", "representative", "stress") for n in range(1, 4)]
    return {
        "schema": "thistinti-performance-capacity-evidence",
        "schema_version": 2,
        "status": "EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION",
        "qualification_result": "NOT_A_PASS",
        "qualification_claim": "ThisTinti 1.0 Qualified — Procurement v1 — P1 — E1",
        "candidate": {
            "release_version": "1.0.0",
            "release_tag": "v1.0.0",
            "source_sha": "a" * 40,
            "artifact_identity": "windows-installer-v1.0.0",
            "artifact_sha256": "b" * 64,
            "edition": "Local",
            "os": "Windows 11 24H2",
            "runtime": "CPython 3.12",
            "hardware": {
                "cpu": "Example CPU",
                "cores": 8,
                "ram_bytes": 16_000_000_000,
                "storage_type": "NVMe SSD",
                "free_storage_bytes_before_run": 200_000_000_000,
            },
            "database": {
                "engine": "PostgreSQL",
                "version": "17",
                "configuration_ref": "evidence:db-config",
            },
        },
        "workload": {
            "manifest_ref": "evidence:workload-manifest",
            "manifest_sha256": "c" * 64,
            "classification": "NON_BLIND_ONLY",
            "blind_or_holdout_used": False,
            "frozen_before_execution": True,
            "sizes": {
                "small": {"documents": 10, "practices": 3},
                "representative": {"documents": 50, "practices": 12},
                "stress": {"documents": 200, "practices": 50},
            },
        },
        "measurements": {
            "installer_bytes": 100_000_000,
            "post_install_bytes": 300_000_000,
            "idle": {
                "window_seconds": 60,
                "cpu_percent": 0.5,
                "ram_bytes": 200_000_000,
                "evidence_refs": ["evidence:idle"],
            },
            "runs": runs,
            "storage_growth": {
                "database_bytes": 500_000_000,
                "canonical_evidence_snapshot_bytes": 350_000_000,
                "logs_bytes": 5_000_000,
                "quarantine_or_temp_bytes": 0,
                "evidence_refs": ["evidence:storage"],
            },
            "backup": {
                "duration_seconds": 30,
                "artifact_bytes": 450_000_000,
                "sha256": "d" * 64,
                "verified": True,
                "evidence_refs": ["evidence:backup"],
            },
            "restore": {
                "duration_seconds": 45,
                "verification_result": "PASS",
                "cross_reference": "#168",
                "evidence_refs": ["evidence:restore"],
            },
        },
        "limits": {
            "hard_product_limits": [{"name": "max_file_bytes", "value": 50_000_000}],
            "tested_limits": [{"name": "representative_practices", "value": 12}],
            "observed_degradation": [],
            "stress_outcome": "DEGRADED_FAIL_CLOSED",
        },
        "claims": {
            "customer_facing_envelope_ref": "evidence:published-envelope",
            "cross_edition_equivalence_claimed": False,
            "unmeasured_scale_claimed": False,
        },
        "findings": [],
        "evidence_index": ["evidence:index"],
        "result": {
            "classification": "MEASURED",
            "blockers": [],
            "residual_limitations": ["Measured on the named hardware only"],
        },
    }


def test_final_structure_can_validate_without_declaring_pass() -> None:
    assert validate(final_manifest(), final=True) == []


def test_legacy_release_identity_is_rejected() -> None:
    data = final_manifest()
    data["candidate"]["release_version"] = "3.4.0-alpha.7-rc.15"
    data["candidate"]["release_tag"] = "v3.4.0-alpha.7-rc.15"
    errors = validate(data, final=True)
    assert any("release_version" in error for error in errors)
    assert any("release_tag" in error for error in errors)


def test_blind_or_holdout_workload_is_rejected() -> None:
    data = final_manifest()
    data["workload"]["blind_or_holdout_used"] = True
    errors = validate(data, final=True)
    assert any("BLIND/HOLDOUT" in error for error in errors)


def test_single_best_run_shortcut_is_rejected() -> None:
    data = final_manifest()
    data["measurements"]["runs"] = [run for run in data["measurements"]["runs"] if run["run_id"].endswith("-1")]
    errors = validate(data, final=True)
    assert sum("requires at least 3 recorded repetitions" in error for error in errors) == 3


def test_missing_canonical_snapshot_storage_measurement_is_rejected() -> None:
    data = final_manifest()
    data["measurements"]["storage_growth"]["canonical_evidence_snapshot_bytes"] = None
    errors = validate(data, final=True)
    assert any("canonical_evidence_snapshot_bytes" in error for error in errors)


def test_unverified_backup_or_restore_is_rejected() -> None:
    data = final_manifest()
    data["measurements"]["backup"]["verified"] = False
    data["measurements"]["restore"]["verification_result"] = "NOT_RUN"
    errors = validate(data, final=True)
    assert any("backup.verified" in error for error in errors)
    assert any("restore.verification_result" in error for error in errors)


def test_unmeasured_scale_claim_is_rejected() -> None:
    data = final_manifest()
    data["claims"]["unmeasured_scale_claimed"] = True
    errors = validate(data, final=True)
    assert any("unmeasured scale claims" in error for error in errors)


def test_cross_edition_equivalence_is_rejected_without_separate_evidence() -> None:
    data = final_manifest()
    data["claims"]["cross_edition_equivalence_claimed"] = True
    errors = validate(data, final=True)
    assert any("cross-edition equivalence" in error for error in errors)


def test_open_release_blocker_is_rejected() -> None:
    data = final_manifest()
    data["findings"] = [{"id": "PERF-1", "release_blocking": True, "status": "OPEN"}]
    errors = validate(data, final=True)
    assert any("release-blocking performance findings" in error for error in errors)


def test_validator_cannot_self_declare_qualification() -> None:
    data = final_manifest()
    data["qualification_result"] = "PASS"
    errors = validate(data, final=True)
    assert any("cannot itself declare qualification PASS" in error for error in errors)
