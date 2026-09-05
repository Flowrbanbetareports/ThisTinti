from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_external_review_findings.py"
SPEC = importlib.util.spec_from_file_location("validate_external_review_findings", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def complete_register() -> dict:
    finding = {
        "id": "EXT-001",
        "title": "Example closed finding",
        "description": "Independent assessor observation.",
        "surface": "reviewed surface",
        "severity": "MEDIUM",
        "materiality": "NON_MATERIAL",
        "remediation_status": "REMEDIATED",
        "remediation_reference": "documented corrective action",
        "remediation_sha": "1" * 40,
        "retest_required": True,
        "retest_status": "PASS",
    }
    candidate = "a" * 40
    artifact = "b" * 64
    environment = "final intended environment"
    common_track = {
        "report_date": "2026-09-02",
        "reviewed_candidate_sha": candidate,
        "reviewed_artifact_sha256": artifact,
        "reviewed_environment": environment,
        "findings": [finding.copy()],
    }
    return {
        "schema": "thistinti-external-review-findings",
        "schema_version": 2,
        "status": "EXTERNAL_REVIEWS_STRUCTURALLY_COMPLETE",
        "release_claim": "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1",
        "release_version": "1.0.0",
        "release_tag": "v1.0.0",
        "candidate_sha": candidate,
        "artifact_sha256": artifact,
        "environment": environment,
        "tracks": {
            "SECURITY": {
                "issue": 134,
                "independent_reviewer": "external reviewer A",
                "reviewer_organisation": "independent organisation A",
                "scope": ["application and intended deployment"],
                "report_reference": "security-report-reference",
                **common_track,
            },
            "PRIVACY_LEGAL": {
                "issue": 135,
                "independent_reviewer": "external reviewer B",
                "reviewer_organisation": "independent organisation B",
                "scope": ["privacy, legal, trademark and release claims"],
                "report_reference": "legal-review-reference",
                **common_track,
            },
        },
        "residual_risks": [],
        "qualification_decision": "NOT_A_PASS",
    }


def test_complete_final_register_is_structurally_valid():
    assert validator.validate(complete_register(), final=True) == []


def test_final_rejects_legacy_prerelease_tag():
    data = complete_register()
    data["release_tag"] = "v3.4.0-alpha.7-rc.15"
    errors = validator.validate(data, final=True)
    assert any("legacy prerelease" in error for error in errors)


def test_final_rejects_missing_independent_track_metadata():
    data = complete_register()
    data["tracks"]["SECURITY"]["independent_reviewer"] = None
    errors = validator.validate(data, final=True)
    assert any("independent_reviewer" in error for error in errors)


def test_final_rejects_stale_track_candidate():
    data = complete_register()
    data["tracks"]["SECURITY"]["reviewed_candidate_sha"] = "c" * 40
    errors = validator.validate(data, final=True)
    assert any("does not match final candidate_sha" in error for error in errors)


def test_final_rejects_stale_track_artifact():
    data = complete_register()
    data["tracks"]["PRIVACY_LEGAL"]["reviewed_artifact_sha256"] = "d" * 64
    errors = validator.validate(data, final=True)
    assert any("does not match final artifact_sha256" in error for error in errors)


def test_final_rejects_mismatched_review_environment():
    data = complete_register()
    data["tracks"]["SECURITY"]["reviewed_environment"] = "old environment"
    errors = validator.validate(data, final=True)
    assert any("reviewed environment does not match" in error for error in errors)


def test_final_rejects_self_declared_pass():
    data = complete_register()
    data["qualification_decision"] = "PASS"
    errors = validator.validate(data, final=True)
    assert any("cannot declare qualification" in error for error in errors)


def test_high_open_security_finding_blocks():
    data = complete_register()
    finding = data["tracks"]["SECURITY"]["findings"][0]
    finding["severity"] = "HIGH"
    finding["remediation_status"] = "OPEN"
    finding["retest_required"] = False
    finding["retest_status"] = "NOT_REQUIRED"
    errors = validator.validate(data, final=True)
    assert any("release-blocking security severity" in error for error in errors)


def test_material_open_privacy_legal_finding_blocks():
    data = complete_register()
    finding = data["tracks"]["PRIVACY_LEGAL"]["findings"][0]
    finding["materiality"] = "MATERIAL"
    finding["remediation_status"] = "IN_PROGRESS"
    finding["retest_required"] = False
    finding["retest_status"] = "NOT_REQUIRED"
    errors = validator.validate(data, final=True)
    assert any("unresolved material privacy/legal" in error for error in errors)


def test_required_retest_must_pass():
    data = complete_register()
    data["tracks"]["SECURITY"]["findings"][0]["retest_status"] = "NOT_RUN"
    errors = validator.validate(data, final=True)
    assert any("required retest has not passed" in error for error in errors)


def test_risk_acceptance_requires_accountable_record():
    data = complete_register()
    finding = data["tracks"]["SECURITY"]["findings"][0]
    finding["remediation_status"] = "RISK_ACCEPTED"
    finding["retest_required"] = False
    finding["retest_status"] = "NOT_REQUIRED"
    errors = validator.validate(data, final=True)
    assert any("risk acceptance record required" in error for error in errors)
