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
    return {
        "schema": "thistinti-external-review-findings",
        "schema_version": 1,
        "status": "EXTERNAL_REVIEWS_COMPLETE",
        "release_claim": "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1",
        "release_version": "1.0.0",
        "release_tag": "v1.0.0",
        "candidate_sha": "a" * 40,
        "environment": "final intended environment",
        "tracks": {
            "SECURITY": {
                "issue": 134,
                "independent_reviewer": "external reviewer A",
                "reviewer_organisation": "independent organisation A",
                "report_date": "2026-09-02",
                "scope": ["application and intended deployment"],
                "report_reference": "security-report-reference",
                "findings": [finding.copy()],
            },
            "PRIVACY_LEGAL": {
                "issue": 135,
                "independent_reviewer": "external reviewer B",
                "reviewer_organisation": "independent organisation B",
                "report_date": "2026-09-02",
                "scope": ["privacy, legal, trademark and release claims"],
                "report_reference": "legal-review-reference",
                "findings": [finding.copy()],
            },
        },
        "residual_risks": [],
        "final_disposition": "PASS",
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
