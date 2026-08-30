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


def frozen_manifest():
    data = load_template()
    data["status"] = "FROZEN"
    data["p1_scope"] = {
        "version": "P1.0",
        "sha256": "a" * 64,
        "approval_ref": "approval:P1.0",
    }
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
    for pool_name, token in zip(("CALIBRATION", "BLIND", "HOLDOUT"), ("3", "4", "5"), strict=True):
        data["pools"][pool_name] = {
            "manifest_id": f"{pool_name.lower()}-v1",
            "sha256": token * 64,
            "sealed": True,
            "case_count": 1,
        }
    data["reviewer_protocol"] = {
        "version": "1",
        "sha256": "6" * 64,
        "reviewers_secured": True,
        "adjudication_protocol_ref": "reviewer-protocol:v1",
    }
    data["freeze"] = {
        "approved": True,
        "approved_by": "real-approver-ref",
        "approved_at": "2026-08-29T18:00:00Z",
        "freeze_ref": "freeze:v1",
    }
    data["external_evidence"]["authorised_case_sources_secured"] = True
    data["external_evidence"]["independent_reviewers_secured"] = True
    return data


def test_preparation_template_is_valid_only_as_preparation():
    data = load_template()
    validate_manifest(data)
    with pytest.raises(ManifestError, match="requires FROZEN"):
        validate_manifest(data, final=True)


def test_frozen_status_cannot_use_preparation_validation_mode():
    data = frozen_manifest()
    with pytest.raises(ManifestError, match="FROZEN requires --final"):
        validate_manifest(data)


def test_frozen_manifest_accepts_complete_exact_same_sha_gate_evidence():
    validate_manifest(frozen_manifest(), final=True)


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


def test_frozen_manifest_rejects_unsealed_blind_pool():
    data = frozen_manifest()
    data["pools"]["BLIND"]["sealed"] = False
    with pytest.raises(ManifestError, match="BLIND.sealed"):
        validate_manifest(data, final=True)


def test_frozen_manifest_rejects_missing_reviewer_independence_precondition():
    data = frozen_manifest()
    data["reviewer_protocol"]["reviewers_secured"] = False
    with pytest.raises(ManifestError, match="reviewers_secured"):
        validate_manifest(data, final=True)


def test_manifest_rejects_failed_required_gate():
    data = frozen_manifest()
    data["required_gate_evidence"][0]["conclusion"] = "failure"
    with pytest.raises(ManifestError, match="expected success"):
        validate_manifest(data, final=True)


def test_manifest_rejects_pool_substitution_shape():
    data = frozen_manifest()
    changed = copy.deepcopy(data)
    changed["pools"]["SHADOW"] = changed["pools"].pop("HOLDOUT")
    with pytest.raises(ManifestError, match="expected exactly"):
        validate_manifest(changed, final=True)
