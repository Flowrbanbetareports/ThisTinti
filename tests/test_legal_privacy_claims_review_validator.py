from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_legal_privacy_claims_review.py"
SPEC = importlib.util.spec_from_file_location("validate_legal_privacy_claims_review", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def final_record() -> dict:
    areas = {
        area: {"disposition": "APPROVED", "evidence_refs": [f"review:{area}"], "limitations": []}
        for area in validator.EXPECTED_AREAS
    }
    return {
        "schema": validator.EXPECTED_SCHEMA,
        "schema_version": 1,
        "status": "INDEPENDENT_REVIEW_COMPLETE",
        "release_version": "1.0.0",
        "release_tag": "v1.0.0",
        "candidate_sha": "a" * 40,
        "release_claim": validator.BOUNDED_CLAIM,
        "reviewer": {
            "name_or_identifier": "independent-reviewer",
            "organisation": "independent-organisation",
            "independence_statement": "No material conflict declared for the recorded scope.",
            "competence_scope": "privacy, legal, trademark and product claims",
            "review_date": "2026-09-02",
            "report_reference": "report:independent-001",
        },
        "material_inventory": [
            {
                "id": "material-001",
                "reference": "docs/reviewed-material.md",
                "version_or_source_sha": "a" * 40,
                "reviewed_at": "2026-09-02T12:00:00Z",
                "sha256": "b" * 64,
            }
        ],
        "review_matrix": areas,
        "findings_register_ref": "external-review-register:001",
        "approved_qualified_wording": validator.BOUNDED_CLAIM + " — subject to recorded limitations.",
        "required_limitations": [],
        "not_reviewed": [],
        "qualification_decision": "NOT_A_PASS",
    }


def test_structurally_complete_final_record_is_not_a_qualification_pass() -> None:
    assert validator.validate(final_record(), final=True) == []


def test_legacy_prerelease_tag_is_rejected() -> None:
    data = final_record()
    data["release_tag"] = "v3.4.0-alpha.7-rc.15"
    assert any("legacy prerelease" in error for error in validator.validate(data, final=True))


def test_missing_review_area_fails_closed() -> None:
    data = final_record()
    data["review_matrix"].pop("economic_claims")
    assert any("missing areas" in error for error in validator.validate(data, final=True))


def test_not_reviewed_or_remediation_required_cannot_be_final() -> None:
    for disposition in ("NOT_REVIEWED", "REMEDIATION_REQUIRED"):
        data = final_record()
        data["review_matrix"]["qualified_claim"]["disposition"] = disposition
        assert any(disposition in error for error in validator.validate(data, final=True))


def test_limited_or_out_of_scope_disposition_requires_reason() -> None:
    for disposition in ("APPROVED_WITH_LIMITATION", "OUT_OF_SCOPE_WITH_REASON"):
        data = final_record()
        data["review_matrix"]["local_first_deployment_claims"]["disposition"] = disposition
        assert any("requires explicit limitation/reason" in error for error in validator.validate(data, final=True))


def test_final_matrix_row_requires_evidence_reference() -> None:
    data = final_record()
    data["review_matrix"]["thistinti_name_trademark"]["evidence_refs"] = []
    assert any("final disposition requires evidence_refs" in error for error in validator.validate(data, final=True))


def test_material_inventory_requires_hash_or_reason() -> None:
    data = final_record()
    data["material_inventory"][0].pop("sha256")
    assert any("sha256 or hash_unavailable_reason" in error for error in validator.validate(data, final=True))


def test_invalid_material_hash_is_rejected() -> None:
    data = final_record()
    data["material_inventory"][0]["sha256"] = "not-a-digest"
    assert any("sha256 must be 64" in error for error in validator.validate(data, final=True))


def test_missing_reviewer_independence_or_findings_register_fails() -> None:
    data = final_record()
    data["reviewer"]["independence_statement"] = None
    data["findings_register_ref"] = None
    errors = validator.validate(data, final=True)
    assert any("independence_statement" in error for error in errors)
    assert any("findings_register_ref" in error for error in errors)


def test_validator_cannot_self_declare_qualification_pass() -> None:
    data = final_record()
    data["qualification_decision"] = "PASS"
    assert any("cannot declare qualification PASS" in error for error in validator.validate(data, final=True))


def test_approved_wording_must_keep_bounded_claim() -> None:
    data = final_record()
    data["approved_qualified_wording"] = "Universal automated compliance platform."
    assert any("bounded P1/E1" in error for error in validator.validate(data, final=True))


def test_preparation_template_shape_can_remain_not_reviewed() -> None:
    data = final_record()
    data["status"] = "PREPARATION_ONLY_NOT_REVIEWED"
    data["candidate_sha"] = None
    data["reviewer"] = {key: None for key in data["reviewer"]}
    data["material_inventory"] = []
    for row in data["review_matrix"].values():
        row["disposition"] = "NOT_REVIEWED"
        row["evidence_refs"] = []
    data["findings_register_ref"] = None
    data["approved_qualified_wording"] = None
    assert validator.validate(deepcopy(data), final=False) == []
