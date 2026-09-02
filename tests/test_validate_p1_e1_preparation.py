from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_p1_e1_preparation.py"
spec = importlib.util.spec_from_file_location("validate_p1_e1_preparation", MODULE_PATH)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def _case(pool="CALIBRATION"):
    return {
        "case_id": "case-001",
        "pool": pool,
        "stratum": "invoice-payment",
        "authorization_status": "verified",
        "authorization_ref": "auth-001",
        "anonymization_status": "not_required_verified",
        "anonymization_method_version": None,
        "anonymization_operator_ref": None,
        "content_hashes": ["a" * 64],
        "source_provenance_ref": "source-001",
        "declared_acquisition_path": "declared-path",
        "declared_parser_path": "declared-parser",
        "ingestion_allowed": True,
        "access_history": [],
    }


def _registry(case):
    manifest = {"manifest_id": "pool-v1", "sha256": "b" * 64, "sealed": True, "sealed_at": "2026-09-02T00:00:00Z"}
    return {
        "schema": "thistinti-p1-e1-case-registry",
        "schema_version": 1,
        "protocol_version": "E1",
        "cases": [case],
        "pool_manifests": {"CALIBRATION": dict(manifest), "BLIND": dict(manifest), "HOLDOUT": dict(manifest)},
    }


def _reviewers():
    return {
        "schema": "thistinti-p1-e1-reviewer-protocol",
        "schema_version": 1,
        "protocol_version": "E1",
        "pool_manifest_sha256": "c" * 64,
        "reviewers": [
            {"reviewer_id": "r1", "competence_attestation_ref": "c1", "conflict_declaration_ref": "x1", "independence_attestation_ref": "i1", "assigned_at": "2026-09-02T00:00:00Z"},
            {"reviewer_id": "r2", "competence_attestation_ref": "c2", "conflict_declaration_ref": "x2", "independence_attestation_ref": "i2", "assigned_at": "2026-09-02T00:00:00Z"},
        ],
        "reference_record_contract": {"must_be_sealed_before_product_exposure": True},
        "adjudication_contract": {"separate_record_required": True, "must_preserve_original_reviews": True},
    }


def test_accepts_eligible_sealed_metadata_without_case_contents():
    validator.validate_registry(_registry(_case()), sealed=True)
    validator.validate_reviewer_protocol(_reviewers(), ready=True)


def test_rejects_ingestion_when_authorisation_is_not_verified():
    case = _case()
    case["authorization_status"] = "pending"
    with pytest.raises(validator.ValidationError, match="ingestion_allowed"):
        validator.validate_registry(_registry(case), sealed=False)


def test_rejects_blind_content_access_during_development():
    case = _case("BLIND")
    case["access_history"] = [{
        "actor_role": "developer",
        "purpose": "debug",
        "timestamp": "2026-09-02T00:00:00Z",
        "content_access": "content",
        "protocol_phase": "DEVELOPMENT",
    }]
    with pytest.raises(validator.ValidationError, match="contamination"):
        validator.validate_registry(_registry(case), sealed=True)


def test_metadata_only_access_does_not_trigger_content_contamination():
    case = _case("HOLDOUT")
    case["access_history"] = [{
        "actor_role": "custodian",
        "purpose": "integrity-check",
        "timestamp": "2026-09-02T00:00:00Z",
        "content_access": "metadata_only",
        "protocol_phase": "PRE_FREEZE",
    }]
    validator.validate_registry(_registry(case), sealed=True)


def test_rejects_same_reviewer_twice():
    data = _reviewers()
    data["reviewers"][1]["reviewer_id"] = "r1"
    with pytest.raises(validator.ValidationError, match="distinct reviewer"):
        validator.validate_reviewer_protocol(data, ready=True)


def test_rejects_adjudication_that_can_overwrite_originals():
    data = _reviewers()
    data["adjudication_contract"]["must_preserve_original_reviews"] = False
    with pytest.raises(validator.ValidationError, match="preserve original"):
        validator.validate_reviewer_protocol(data, ready=False)
