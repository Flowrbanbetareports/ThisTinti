from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "validate_exit_portability_reconstruction_evidence.py"
SPEC = importlib.util.spec_from_file_location("validate_exit_portability", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate = MODULE.validate


def final_manifest() -> dict:
    return {
        "schema": "thistinti-exit-portability-reconstruction-evidence",
        "schema_version": 1,
        "status": "EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION",
        "qualification_result": "NOT_A_PASS",
        "candidate": {
            "release_version": "1.0.0",
            "release_tag": "v1.0.0",
            "source_sha": "a" * 40,
            "candidate_id": "qualified-candidate",
            "release_artifact_refs": ["release:v1.0.0/windows-installer"],
        },
        "package": {
            "format": "thistinti-backup-v1",
            "producer_release": "1.0.0",
            "package_ref": "evidence:backup-package",
            "package_sha256": "b" * 64,
            "manifest_ref": "evidence:backup-manifest",
            "storage_included": True,
            "database_engine": "postgresql",
            "database_version": "17",
        },
        "canonical_evidence_snapshots": {
            "applicable": True,
            "pre_loss_identity_ref": "evidence:pre-loss-canonical-identity",
            "snapshot_row_presence": "PASS",
            "document_tenant_linkage": "PASS",
            "canonical_byte_hash_match_after_restore": "PASS",
            "reviewer_export_identity_match": "PASS",
            "filesystem_fallback_not_used_as_substitute": "PASS",
            "offline_inspection_method_documented": "PASS",
            "offline_inspection_result": "PASS",
            "evidence_refs": ["evidence:canonical-snapshots"],
        },
        "clean_machine": {
            "environment_id": "clean-win-01",
            "is_source_state_absent_before_test": True,
            "os_runtime": "Windows 11 24H2",
            "prerequisite_tools": [
                {"name": "pg_restore", "version": "17", "purpose": "restore"},
                {"name": "psql", "version": "17", "purpose": "offline inspection"},
            ],
        },
        "reconstruction": {
            "linked_recovery_evidence_ref": "evidence:recovery-final",
            "package_identity_verified": "PASS",
            "manifest_entry_integrity": "PASS",
            "restore_on_clean_target": "PASS",
            "storage_integrity": "PASS",
            "canonical_evidence_integrity": "PASS",
            "document_fact_finding_judgment_integrity": "PASS",
            "application_read_only_smoke": "PASS",
            "measured_elapsed_seconds": 321.5,
            "manual_interventions": [],
            "evidence_refs": ["evidence:reconstruction"],
        },
        "offline_exit_inspection": {
            "thistinti_service_running": False,
            "container_openable": "PASS",
            "manifest_json_readable": "PASS",
            "integrity_metadata_inspectable": "PASS",
            "source_documents_extractable": "PASS",
            "database_snapshot_method_documented": "PASS",
            "canonical_snapshot_records": "PASS",
            "semantic_records": "PASS",
            "identifier_correlation": "PASS",
            "provenance_traceability": "PASS",
            "required_offline_method": "documented pg_restore/psql + manifest procedure",
            "opaque_or_unsupported_fields": [],
            "evidence_refs": ["evidence:offline-inspection"],
        },
        "compatibility": {
            "consumer_release_tested": "1.0.0",
            "forward_compatibility_claim": "NO_UNTESTED_CLAIM",
            "backward_compatibility_claim": "NO_UNTESTED_CLAIM",
            "database_downgrade_claim": "NO_UNTESTED_CLAIM",
            "original_package_preserved": True,
            "known_prerequisites": [],
            "unsupported_paths": ["downgrade"],
            "maintenance_eol_policy_ref": "docs:maintenance-1.0.x",
        },
        "findings": [],
        "operator_attestation_ref": "evidence:operator-attestation",
        "evidence_index": ["evidence:index"],
        "limitations": [],
    }


def test_final_structure_can_validate_without_declaring_pass() -> None:
    assert validate(final_manifest(), final=True) == []


def test_legacy_prerelease_identity_is_rejected() -> None:
    data = final_manifest()
    data["candidate"]["release_version"] = "3.4.0-alpha.7-rc.15"
    data["candidate"]["release_tag"] = "v3.4.0-alpha.7-rc.15"
    errors = validate(data, final=True)
    assert any("release_version" in error for error in errors)
    assert any("release_tag" in error for error in errors)


def test_placeholder_or_short_candidate_identity_is_rejected() -> None:
    data = final_manifest()
    data["candidate"]["source_sha"] = "deadbeef"
    data["candidate"]["release_artifact_refs"] = ["<artifact-ref>"]
    errors = validate(data, final=True)
    assert any("source_sha" in error for error in errors)
    assert any("release_artifact_refs" in error for error in errors)


def test_database_presence_is_not_canonical_snapshot_reconstruction_proof() -> None:
    data = final_manifest()
    data["canonical_evidence_snapshots"]["canonical_byte_hash_match_after_restore"] = "NOT_EXECUTED"
    data["canonical_evidence_snapshots"]["filesystem_fallback_not_used_as_substitute"] = "NOT_EXECUTED"
    errors = validate(data, final=True)
    assert any("canonical_byte_hash_match_after_restore" in error for error in errors)
    assert any("filesystem_fallback_not_used_as_substitute" in error for error in errors)


def test_restore_on_original_machine_is_rejected() -> None:
    data = final_manifest()
    data["clean_machine"]["is_source_state_absent_before_test"] = False
    errors = validate(data, final=True)
    assert any("original source state absent" in error for error in errors)


def test_running_application_is_not_offline_portability() -> None:
    data = final_manifest()
    data["offline_exit_inspection"]["thistinti_service_running"] = True
    errors = validate(data, final=True)
    assert any("without a running ThisTinti service" in error for error in errors)


def test_unmeasured_restore_time_is_rejected() -> None:
    data = final_manifest()
    data["reconstruction"]["measured_elapsed_seconds"] = None
    errors = validate(data, final=True)
    assert any("measured_elapsed_seconds" in error for error in errors)


def test_untested_compatibility_claim_is_rejected() -> None:
    data = final_manifest()
    data["compatibility"]["database_downgrade_claim"] = "SUPPORTED"
    errors = validate(data, final=True)
    assert any("database_downgrade_claim" in error for error in errors)


def test_open_release_blocker_is_rejected() -> None:
    data = final_manifest()
    data["findings"] = [{"id": "REC-1", "release_blocking": True, "status": "OPEN"}]
    errors = validate(data, final=True)
    assert any("release-blocking findings" in error for error in errors)


def test_validator_cannot_be_used_to_self_declare_qualification() -> None:
    data = final_manifest()
    data["qualification_result"] = "PASS"
    errors = validate(data, final=True)
    assert any("cannot itself declare qualification PASS" in error for error in errors)
