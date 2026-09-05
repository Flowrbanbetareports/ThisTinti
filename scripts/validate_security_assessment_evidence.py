#!/usr/bin/env python3
"""Fail-closed structural validator for independent security assessment evidence.

This validator checks internal consistency only. It cannot prove assessor
independence, that testing happened, or that a security conclusion is correct.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"^<.*>$")

SCHEMA_VERSION = "security-assessment-evidence.v0.1"
OFFICIAL_RELEASE_VERSION = "1.0.0"
OFFICIAL_RELEASE_TAG = "v1.0.0"
ALLOWED_STATUS = {"PREPARATION_ONLY", "ASSESSMENT_COMPLETE"}
REQUIRED_COVERAGE = frozenset(
    {
        "attack_surface",
        "auth_session_csrf_csp_cors_proxy",
        "tenant_database_isolation",
        "malicious_document_parser_ocr",
        "secrets_ci_release_supply_chain",
        "backup_restore_security",
        "incident_vulnerability_disclosure",
        "evidence_integrity",
        "canonical_evidence_snapshot_security",
    }
)
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "OBSERVATION"}
FINDING_STATUSES = {
    "OPEN",
    "FIXED_PENDING_RETEST",
    "RETESTED_PASS",
    "ACCEPTED_RESIDUAL",
    "REJECTED_NOT_APPLICABLE",
}
BLOCKING_SEVERITIES = {"CRITICAL", "HIGH"}


class SecurityEvidenceError(ValueError):
    pass


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SecurityEvidenceError(f"{path}: expected object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise SecurityEvidenceError(f"{path}: expected array")
    return value


def _string(value: Any, path: str, *, allow_placeholder: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise SecurityEvidenceError(f"{path}: expected non-empty string")
    if not allow_placeholder and PLACEHOLDER.fullmatch(value):
        raise SecurityEvidenceError(f"{path}: unresolved placeholder")
    return value


def _sha(value: Any, path: str, pattern: re.Pattern[str], *, allow_placeholder: bool) -> str:
    text = _string(value, path, allow_placeholder=allow_placeholder)
    if allow_placeholder and PLACEHOLDER.fullmatch(text):
        return text
    if not pattern.fullmatch(text):
        raise SecurityEvidenceError(f"{path}: invalid hash format")
    return text


def _refs(value: Any, path: str, *, required: bool) -> list[str]:
    refs = _array(value, path)
    if required and not refs:
        raise SecurityEvidenceError(f"{path}: expected at least one evidence reference")
    for index, ref in enumerate(refs):
        _string(ref, f"{path}[{index}]")
    if len(refs) != len(set(refs)):
        raise SecurityEvidenceError(f"{path}: duplicate evidence reference")
    return refs


def validate_security_evidence(data: dict[str, Any], *, final: bool = False) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SecurityEvidenceError("schema_version: unsupported schema")
    if data.get("qualification_claim") != ("ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1"):
        raise SecurityEvidenceError("qualification_claim: unexpected claim")

    status = data.get("status")
    if status not in ALLOWED_STATUS:
        raise SecurityEvidenceError("status: invalid value")
    if status == "ASSESSMENT_COMPLETE" and not final:
        raise SecurityEvidenceError("status: ASSESSMENT_COMPLETE requires --final validation")
    if final and status != "ASSESSMENT_COMPLETE":
        raise SecurityEvidenceError("status: final validation requires ASSESSMENT_COMPLETE")

    candidate = _mapping(data.get("candidate"), "candidate")
    source_sha = _sha(
        candidate.get("source_sha"),
        "candidate.source_sha",
        SHA40,
        allow_placeholder=not final,
    )
    release_version = _string(
        candidate.get("release_version"),
        "candidate.release_version",
        allow_placeholder=not final,
    )
    release_tag = _string(
        candidate.get("release_tag"),
        "candidate.release_tag",
        allow_placeholder=not final,
    )
    if final and release_version != OFFICIAL_RELEASE_VERSION:
        raise SecurityEvidenceError(
            f"candidate.release_version: final evidence requires {OFFICIAL_RELEASE_VERSION}"
        )
    if final and release_tag != OFFICIAL_RELEASE_TAG:
        raise SecurityEvidenceError(
            f"candidate.release_tag: final evidence requires {OFFICIAL_RELEASE_TAG}"
        )

    artifacts = _array(candidate.get("artifacts"), "candidate.artifacts")
    if final and not artifacts:
        raise SecurityEvidenceError("candidate.artifacts: final evidence requires artifacts")
    seen_artifacts: set[str] = set()
    for index, artifact in enumerate(artifacts):
        item = _mapping(artifact, f"candidate.artifacts[{index}]")
        artifact_id = _string(
            item.get("artifact_id"),
            f"candidate.artifacts[{index}].artifact_id",
            allow_placeholder=not final,
        )
        if artifact_id in seen_artifacts:
            raise SecurityEvidenceError(f"candidate.artifacts[{index}].artifact_id: duplicate artifact")
        seen_artifacts.add(artifact_id)
        _sha(
            item.get("sha256"),
            f"candidate.artifacts[{index}].sha256",
            SHA256,
            allow_placeholder=not final,
        )

    environment = _mapping(data.get("environment"), "environment")
    for field in ("deployment_topology", "database", "os_runtime"):
        _string(environment.get(field), f"environment.{field}", allow_placeholder=not final)

    assessor = _mapping(data.get("assessor"), "assessor")
    for field in ("organisation", "lead_assessor", "independence_declaration", "assessment_window"):
        _string(assessor.get(field), f"assessor.{field}", allow_placeholder=not final)
    report_ref: str | None = None
    if final:
        report_ref = _string(assessor.get("report_ref"), "assessor.report_ref")

    coverage = _array(data.get("coverage"), "coverage")
    seen_coverage: set[str] = set()
    for index, row in enumerate(coverage):
        item = _mapping(row, f"coverage[{index}]")
        area = _string(item.get("area"), f"coverage[{index}].area")
        if area not in REQUIRED_COVERAGE:
            raise SecurityEvidenceError(f"coverage[{index}].area: unknown area")
        if area in seen_coverage:
            raise SecurityEvidenceError(f"coverage[{index}].area: duplicate area")
        seen_coverage.add(area)
        result = item.get("result")
        if result not in {"NOT_RUN", "TESTED"}:
            raise SecurityEvidenceError(f"coverage[{index}].result: expected NOT_RUN or TESTED")
        _refs(item.get("evidence_refs"), f"coverage[{index}].evidence_refs", required=final)
        if final and result != "TESTED":
            raise SecurityEvidenceError(f"coverage[{index}].result: final evidence requires TESTED")
    missing_coverage = sorted(REQUIRED_COVERAGE - seen_coverage)
    if missing_coverage:
        raise SecurityEvidenceError("coverage: missing required areas: " + ", ".join(missing_coverage))

    findings = _array(data.get("findings"), "findings")
    seen_findings: set[str] = set()
    for index, finding in enumerate(findings):
        item = _mapping(finding, f"findings[{index}]")
        prefix = f"findings[{index}]"
        finding_id = _string(item.get("finding_id"), f"{prefix}.finding_id")
        if finding_id in seen_findings:
            raise SecurityEvidenceError(f"{prefix}.finding_id: duplicate finding")
        seen_findings.add(finding_id)

        severity = item.get("severity")
        if severity not in SEVERITIES:
            raise SecurityEvidenceError(f"{prefix}.severity: invalid value")
        status_value = item.get("status")
        if status_value not in FINDING_STATUSES:
            raise SecurityEvidenceError(f"{prefix}.status: invalid value")

        _string(item.get("title"), f"{prefix}.title")
        _string(item.get("reproduction_or_basis"), f"{prefix}.reproduction_or_basis")
        _refs(item.get("evidence_refs"), f"{prefix}.evidence_refs", required=True)

        qualification_impact = item.get("qualification_impact")
        if qualification_impact not in {"BLOCKER", "CONDITIONAL", "NON_BLOCKING"}:
            raise SecurityEvidenceError(f"{prefix}.qualification_impact: invalid value")
        evidence_integrity = item.get("evidence_integrity_impact")
        if not isinstance(evidence_integrity, bool):
            raise SecurityEvidenceError(f"{prefix}.evidence_integrity_impact: expected boolean")

        release_blocking = severity in BLOCKING_SEVERITIES or qualification_impact == "BLOCKER"
        if evidence_integrity:
            release_blocking = True

        if final and status_value in {"OPEN", "FIXED_PENDING_RETEST"}:
            raise SecurityEvidenceError(f"{prefix}.status: final evidence requires a terminal decision")
        if final and evidence_integrity and status_value != "RETESTED_PASS":
            raise SecurityEvidenceError(f"{prefix}.status: evidence-integrity blocker requires RETESTED_PASS")
        if (
            final
            and release_blocking
            and status_value
            not in {
                "RETESTED_PASS",
                "REJECTED_NOT_APPLICABLE",
            }
        ):
            raise SecurityEvidenceError(f"{prefix}.status: release blocker requires retest or rejection")

        if status_value == "RETESTED_PASS":
            retest_sha = _sha(
                item.get("retest_candidate_sha"),
                f"{prefix}.retest_candidate_sha",
                SHA40,
                allow_placeholder=False,
            )
            if not PLACEHOLDER.fullmatch(str(source_sha)) and retest_sha != source_sha:
                raise SecurityEvidenceError(f"{prefix}.retest_candidate_sha: stale-candidate retest")
            _refs(item.get("retest_evidence_refs"), f"{prefix}.retest_evidence_refs", required=True)
        elif final and status_value == "ACCEPTED_RESIDUAL":
            _string(item.get("residual_risk_rationale"), f"{prefix}.residual_risk_rationale")
            _string(item.get("residual_risk_approval_ref"), f"{prefix}.residual_risk_approval_ref")
        elif final and status_value == "REJECTED_NOT_APPLICABLE":
            _string(item.get("rejection_basis"), f"{prefix}.rejection_basis")
            _string(item.get("rejection_approval_ref"), f"{prefix}.rejection_approval_ref")

    if final:
        final_report_refs = _refs(
            data.get("final_report_evidence_refs"),
            "final_report_evidence_refs",
            required=True,
        )
        if report_ref not in final_report_refs:
            raise SecurityEvidenceError("final_report_evidence_refs: assessor report_ref is not referenced")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument(
        "--final",
        action="store_true",
        help="enforce completed independent-assessment evidence preconditions",
    )
    args = parser.parse_args()

    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SecurityEvidenceError("root: expected object")
    validate_security_evidence(data, final=args.final)
    print("Security assessment evidence validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())