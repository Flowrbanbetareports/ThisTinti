from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "validate_security_assessment_evidence.py"
SPEC = importlib.util.spec_from_file_location("validate_security_assessment_evidence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SecurityEvidenceError = MODULE.SecurityEvidenceError
validate_security_evidence = MODULE.validate_security_evidence

SHA = "a" * 40
HASH = "b" * 64


def _complete_evidence() -> dict:
    return {
        "schema_version": "security-assessment-evidence.v0.1",
        "qualification_claim": "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1",
        "status": "ASSESSMENT_COMPLETE",
        "candidate": {
            "source_sha": SHA,
            "release_version": "1.0.0",
            "release_tag": "v1.0.0",
            "artifacts": [{"artifact_id": "windows-installer", "sha256": HASH}],
        },
        "environment": {
            "deployment_topology": "local Windows client plus PostgreSQL",
            "database": "PostgreSQL test environment",
            "os_runtime": "Windows 11",
        },
        "assessor": {
            "organisation": "Independent Assessor Ltd",
            "lead_assessor": "A-001",
            "independence_declaration": "No implementation role or release approval authority.",
            "assessment_window": "2026-08-30/2026-08-31",
            "report_ref": "SEC-REPORT-001",
        },
        "coverage": [
            {"area": area, "result": "TESTED", "evidence_refs": [f"EV-{index:02d}"]}
            for index, area in enumerate(sorted(MODULE.REQUIRED_COVERAGE), start=1)
        ],
        "findings": [],
        "final_report_evidence_refs": ["SEC-REPORT-001"],
    }


def test_complete_structural_packet_passes_final_validation() -> None:
    validate_security_evidence(_complete_evidence(), final=True)


def test_complete_status_cannot_use_preparation_validation() -> None:
    with pytest.raises(SecurityEvidenceError, match="requires --final"):
        validate_security_evidence(_complete_evidence())


def test_missing_required_coverage_fails_closed() -> None:
    data = _complete_evidence()
    data["coverage"].pop()

    with pytest.raises(SecurityEvidenceError, match="missing required areas"):
        validate_security_evidence(data, final=True)


def test_canonical_evidence_snapshot_security_is_mandatory() -> None:
    data = _complete_evidence()
    data["coverage"] = [
        row for row in data["coverage"] if row["area"] != "canonical_evidence_snapshot_security"
    ]

    with pytest.raises(SecurityEvidenceError, match="canonical_evidence_snapshot_security"):
        validate_security_evidence(data, final=True)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("release_version", "3.4.0-alpha.7-rc.15", "final evidence requires 1.0.0"),
        ("release_tag", "v3.4.0-alpha.7-rc.15", "final evidence requires v1.0.0"),
    ],
)
def test_legacy_prerelease_identity_cannot_substitute_for_official_v1(
    field: str, value: str, message: str
) -> None:
    data = _complete_evidence()
    data["candidate"][field] = value

    with pytest.raises(SecurityEvidenceError, match=message):
        validate_security_evidence(data, final=True)


def test_stale_retest_candidate_is_rejected() -> None:
    data = _complete_evidence()
    data["findings"] = [
        {
            "finding_id": "SEC-001",
            "title": "High finding",
            "severity": "HIGH",
            "qualification_impact": "BLOCKER",
            "evidence_integrity_impact": False,
            "reproduction_or_basis": "Reproducer",
            "evidence_refs": ["FINDING-001"],
            "status": "RETESTED_PASS",
            "retest_candidate_sha": "c" * 40,
            "retest_evidence_refs": ["RETEST-001"],
        }
    ]

    with pytest.raises(SecurityEvidenceError, match="stale-candidate retest"):
        validate_security_evidence(data, final=True)


@pytest.mark.parametrize("status", ["OPEN", "FIXED_PENDING_RETEST"])
def test_high_findings_cannot_remain_unresolved(status: str) -> None:
    data = _complete_evidence()
    data["findings"] = [
        {
            "finding_id": "SEC-001",
            "title": "High finding",
            "severity": "HIGH",
            "qualification_impact": "BLOCKER",
            "evidence_integrity_impact": False,
            "reproduction_or_basis": "Reproducer",
            "evidence_refs": ["FINDING-001"],
            "status": status,
        }
    ]

    with pytest.raises(SecurityEvidenceError, match="terminal decision"):
        validate_security_evidence(data, final=True)


def test_evidence_integrity_blocker_requires_retested_pass() -> None:
    data = _complete_evidence()
    data["findings"] = [
        {
            "finding_id": "SEC-001",
            "title": "Evidence substitution",
            "severity": "MEDIUM",
            "qualification_impact": "CONDITIONAL",
            "evidence_integrity_impact": True,
            "reproduction_or_basis": "Reproducer",
            "evidence_refs": ["FINDING-001"],
            "status": "ACCEPTED_RESIDUAL",
            "residual_risk_rationale": "Accepted",
            "residual_risk_approval_ref": "RISK-001",
        }
    ]

    with pytest.raises(SecurityEvidenceError, match="evidence-integrity blocker"):
        validate_security_evidence(data, final=True)


def test_high_residual_acceptance_is_rejected_for_final_packet() -> None:
    data = _complete_evidence()
    data["findings"] = [
        {
            "finding_id": "SEC-001",
            "title": "High finding",
            "severity": "HIGH",
            "qualification_impact": "BLOCKER",
            "evidence_integrity_impact": False,
            "reproduction_or_basis": "Reproducer",
            "evidence_refs": ["FINDING-001"],
            "status": "ACCEPTED_RESIDUAL",
            "residual_risk_rationale": "Proposed acceptance",
            "residual_risk_approval_ref": "RISK-001",
        }
    ]

    with pytest.raises(SecurityEvidenceError, match="release blocker requires retest or rejection"):
        validate_security_evidence(data, final=True)


def test_nonblocking_open_finding_is_not_silently_carried_into_final_packet() -> None:
    data = _complete_evidence()
    data["findings"] = [
        {
            "finding_id": "SEC-LOW-001",
            "title": "Low finding",
            "severity": "LOW",
            "qualification_impact": "NON_BLOCKING",
            "evidence_integrity_impact": False,
            "reproduction_or_basis": "Observation",
            "evidence_refs": ["FINDING-LOW-001"],
            "status": "OPEN",
        }
    ]

    with pytest.raises(SecurityEvidenceError, match="terminal decision"):
        validate_security_evidence(data, final=True)


def test_nonblocking_residual_decision_still_requires_approval_trace() -> None:
    data = _complete_evidence()
    data["findings"] = [
        {
            "finding_id": "SEC-LOW-001",
            "title": "Low finding",
            "severity": "LOW",
            "qualification_impact": "NON_BLOCKING",
            "evidence_integrity_impact": False,
            "reproduction_or_basis": "Observation",
            "evidence_refs": ["FINDING-LOW-001"],
            "status": "ACCEPTED_RESIDUAL",
            "residual_risk_rationale": "",
            "residual_risk_approval_ref": "",
        }
    ]

    with pytest.raises(SecurityEvidenceError, match="residual_risk_rationale"):
        validate_security_evidence(data, final=True)


def test_high_blocker_cannot_be_residual_risk_accepted() -> None:
    data = _complete_evidence()
    data["findings"] = [
        {
            "finding_id": "SEC-HIGH-001",
            "title": "High finding",
            "severity": "HIGH",
            "qualification_impact": "BLOCKER",
            "evidence_integrity_impact": False,
            "reproduction_or_basis": "Reproducer",
            "evidence_refs": ["FINDING-HIGH-001"],
            "status": "ACCEPTED_RESIDUAL",
            "residual_risk_rationale": "Proposed acceptance",
            "residual_risk_approval_ref": "RISK-001",
        }
    ]

    with pytest.raises(SecurityEvidenceError, match="release blocker requires retest or rejection"):
        validate_security_evidence(data, final=True)


def test_duplicate_artifact_identity_is_rejected() -> None:
    data = _complete_evidence()
    data["candidate"]["artifacts"].append(copy.deepcopy(data["candidate"]["artifacts"][0]))

    with pytest.raises(SecurityEvidenceError, match="duplicate artifact"):
        validate_security_evidence(data, final=True)


def test_assessor_report_must_be_in_final_evidence_index() -> None:
    data = _complete_evidence()
    data["final_report_evidence_refs"] = ["SOME-OTHER-REPORT"]

    with pytest.raises(SecurityEvidenceError, match="assessor report_ref is not referenced"):
        validate_security_evidence(data, final=True)