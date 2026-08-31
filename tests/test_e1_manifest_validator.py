import copy
import json
from pathlib import Path

import pytest

from scripts.validate_e1_manifest import (
    REQUIRED_QUALIFICATION_CHECKS,
    ManifestError,
    validate_manifest,
)

TEMPLATE = Path("docs/qualification/e1-manifest.template.json")


def load_template():
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def pre_calibration_manifest():
    data = load_template()
    data["p1_scope"] = {
        "version": "P1.0",
        "sha256": "a" * 64,
        "approval_ref": "approval:P1.0",
    }
    pool_sizes = {"CALIBRATION": 5, "BLIND": 20, "HOLDOUT": 1}
    for index, pool_name in enumerate(("CALIBRATION", "BLIND", "HOLDOUT"), start=3):
        pool = data["pools"][pool_name]
        pool.update(
            {
                "manifest_id": f"{pool_name.lower()}-v1",
                "sha256": str(index) * 64,
                "sealed": True,
                "sealed_at": f"2026-08-29T17:0{index}:00Z",
                "case_count": pool_sizes[pool_name],
                "authorization_evidence_ref": f"auth:{pool_name.lower()}",
                "anonymization_evidence_ref": f"anon:{pool_name.lower()}",
                "custodian_ref": "custodian:external-1",
                "opened_at": None,
            }
        )
    data["segregation"] = {
        "pool_assignment_frozen_before_calibration": True,
        "cross_pool_similarity_check": {
            "status": "PASSED",
            "evidence_ref": "segregation:similarity-v1",
        },
        "access_control_evidence_ref": "segregation:acl-v1",
        "assignment_evidence_ref": "segregation:assignment-v1",
    }
    data["timeline"] = {
        "pools_sealed_at": "2026-08-29T17:10:00Z",
        "calibration_started_at": None,
        "blind_started_at": None,
        "holdout_started_at": None,
    }
    data["reviewer_protocol"] = {
        "version": "1",
        "sha256": "6" * 64,
        "reviewers_secured": True,
        "reviewer_refs": ["reviewer:1", "reviewer:2"],
        "independent_review_required": True,
        "reviewers_must_not_see_thistinti_output_before_submission": True,
        "adjudication_protocol_ref": "reviewer-protocol:v1",
    }
    data["external_evidence"]["authorised_case_sources_secured"] = True
    data["external_evidence"]["independent_reviewers_secured"] = True
    return data


def frozen_manifest():
    data = pre_calibration_manifest()
    data["status"] = "FROZEN"
    data["candidate"]["source_sha"] = "b" * 40
    data["candidate"]["release_version"] = "1.0.0-rc.1"
    data["candidate"]["engine_version"] = "1.0.0-rc.1"
    data["candidate"]["qualification_config_sha256"] = "c" * 64
    data["candidate"]["parser_set"] = [{"id": "structured-json", "version": "1", "sha256": "d" * 64}]
    for component, token in zip(
        ("rule_pack", "practice_model", "company_profile", "provenance_matrix"),
        ("e", "f", "1", "2"),
        strict=True,
    ):
        data["candidate"][component] = {"version": "1", "sha256": token * 64}
    data["required_gate_evidence"] = [
        {
            "check": check,
            "source_sha": data["candidate"]["source_sha"],
            "conclusion": "success",
        }
        for check in sorted(REQUIRED_QUALIFICATION_CHECKS)
    ]
    data["timeline"]["calibration_started_at"] = "2026-08-29T18:00:00Z"
    data["timeline"]["blind_started_at"] = "2026-08-30T10:00:00Z"
    data["timeline"]["holdout_started_at"] = "2026-08-30T18:00:00Z"
    data["pools"]["BLIND"]["opened_at"] = "2026-08-30T10:00:00Z"
    data["pools"]["HOLDOUT"]["opened_at"] = "2026-08-30T18:00:00Z"
    data["freeze"] = {
        "approved": True,
        "approved_by": "real-approver-ref",
        "approved_at": "2026-08-30T20:00:00Z",
        "freeze_ref": "freeze:v1",
    }
    return data


def test_preparation_template_is_valid_only_as_preparation():
    data = load_template()
    validate_manifest(data)
    with pytest.raises(ManifestError, match="requires FROZEN"):
        validate_manifest(data, final=True)


def test_pre_calibration_manifest_accepts_complete_declared_segregation():
    validate_manifest(pre_calibration_manifest(), pre_calibration=True)


def test_pre_calibration_rejects_unsealed_holdout():
    data = pre_calibration_manifest()
    data["pools"]["HOLDOUT"]["sealed"] = False
    with pytest.raises(ManifestError, match="HOLDOUT.sealed"):
        validate_manifest(data, pre_calibration=True)


def test_pre_calibration_rejects_blind_developer_access():
    data = pre_calibration_manifest()
    data["pools"]["BLIND"]["access_policy"]["developer_access_before_release"] = True
    with pytest.raises(ManifestError, match="developer_access_before_release"):
        validate_manifest(data, pre_calibration=True)


def test_pre_calibration_rejects_started_calibration():
    data = pre_calibration_manifest()
    data["timeline"]["calibration_started_at"] = "2026-08-29T18:00:00Z"
    with pytest.raises(ManifestError, match="calibration_started_at"):
        validate_manifest(data, pre_calibration=True)


def test_pre_calibration_rejects_missing_cross_pool_check():
    data = pre_calibration_manifest()
    data["segregation"]["cross_pool_similarity_check"]["status"] = "NOT_RUN"
    with pytest.raises(ManifestError, match="cross_pool_similarity_check.status"):
        validate_manifest(data, pre_calibration=True)


def test_pre_calibration_rejects_duplicate_pool_hash():
    data = pre_calibration_manifest()
    data["pools"]["HOLDOUT"]["sha256"] = data["pools"]["BLIND"]["sha256"]
    with pytest.raises(ManifestError, match="duplicate across pools"):
        validate_manifest(data, pre_calibration=True)


def test_pre_calibration_rejects_missing_two_reviewer_refs():
    data = pre_calibration_manifest()
    data["reviewer_protocol"]["reviewer_refs"] = ["reviewer:1"]
    with pytest.raises(ManifestError, match="at least two reviewers"):
        validate_manifest(data, pre_calibration=True)


def test_pre_calibration_rejects_opened_blind_pool():
    data = pre_calibration_manifest()
    data["pools"]["BLIND"]["opened_at"] = "2026-08-29T18:00:00Z"
    with pytest.raises(ManifestError, match="BLIND.opened_at"):
        validate_manifest(data, pre_calibration=True)


def test_frozen_status_cannot_use_preparation_validation_mode():
    data = frozen_manifest()
    with pytest.raises(ManifestError, match="FROZEN requires --final"):
        validate_manifest(data)


def test_frozen_manifest_accepts_complete_exact_same_sha_gate_evidence():
    validate_manifest(frozen_manifest(), final=True)


def test_final_allows_recorded_pool_open_times_after_segregation():
    data = frozen_manifest()
    validate_manifest(data, final=True)


def test_frozen_manifest_rejects_missing_gate_evidence():
    data = frozen_manifest()
    data["required_gate_evidence"] = []
    with pytest.raises(ManifestError, match="requires gate evidence"):
        validate_manifest(data, final=True)


def test_frozen_manifest_rejects_incomplete_required_gate_set():
    data = frozen_manifest()
    data["required_gate_evidence"] = [
        gate for gate in data["required_gate_evidence"] if gate["check"] != "dependency-audit"
    ]
    with pytest.raises(ManifestError, match=r"missing required checks: dependency-audit"):
        validate_manifest(data, final=True)


def test_frozen_manifest_rejects_duplicate_gate_identity():
    data = frozen_manifest()
    data["required_gate_evidence"].append(copy.deepcopy(data["required_gate_evidence"][0]))
    with pytest.raises(ManifestError, match="duplicate check"):
        validate_manifest(data, final=True)


def test_frozen_manifest_rejects_stale_gate_sha():
    data = frozen_manifest()
    data["required_gate_evidence"][0]["source_sha"] = "9" * 40
    with pytest.raises(ManifestError, match="stale-SHA evidence"):
        validate_manifest(data, final=True)


@pytest.mark.parametrize(
    ("pool_name", "case_count", "expected"),
    [
        ("CALIBRATION", 4, "5-10 cases"),
        ("CALIBRATION", 11, "5-10 cases"),
        ("BLIND", 19, "20-25 cases"),
        ("BLIND", 26, "20-25 cases"),
    ],
)
def test_frozen_manifest_rejects_out_of_protocol_pool_sizes(pool_name, case_count, expected):
    data = frozen_manifest()
    data["pools"][pool_name]["case_count"] = case_count
    with pytest.raises(ManifestError, match=expected):
        validate_manifest(data, final=True)


def test_manifest_rejects_pool_substitution_shape():
    data = frozen_manifest()
    changed = copy.deepcopy(data)
    changed["pools"]["SHADOW"] = changed["pools"].pop("HOLDOUT")
    with pytest.raises(ManifestError, match="expected exactly"):
        validate_manifest(changed, final=True)


def test_manifest_rejects_weakened_claim_boundary():
    data = load_template()
    data["claim_boundary"]["not_blind_material_cannot_substitute_blind_or_holdout"] = False
    with pytest.raises(ManifestError, match="not_blind_material"):
        validate_manifest(data)
