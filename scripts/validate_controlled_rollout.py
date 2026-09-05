#!/usr/bin/env python3
"""Fail-closed structural validator for the ThisTinti 1.0 controlled rollout record.

This validator checks structure, exact-candidate binding and release-blocker handling. It does
not authenticate participants, companies, authorisations or observations and cannot declare
ThisTinti qualified.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

EXPECTED_SCHEMA = "thistinti-controlled-rollout"
BLOCKING_SEVERITIES = {"CRITICAL", "HIGH", "QUALIFICATION_BLOCKER"}


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _is_sha40(value: Any) -> bool:
    return isinstance(value, str) and SHA40.fullmatch(value) is not None


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _is_utc(value: Any) -> bool:
    return isinstance(value, str) and RFC3339_UTC.fullmatch(value) is not None


def validate(data: dict[str, Any], final: bool = False) -> list[str]:
    errors: list[str] = []

    _require(data.get("schema") == EXPECTED_SCHEMA, "invalid schema", errors)
    _require(data.get("schema_version") == 1, "schema_version must be 1", errors)
    _require(data.get("release_version") == "1.0.0", "release_version must be exactly 1.0.0", errors)
    _require(data.get("release_tag") == "v1.0.0", "release_tag must be exactly v1.0.0", errors)
    _require(data.get("blind_holdout_used") is False, "BLIND/HOLDOUT material cannot be used for controlled rollout", errors)
    _require(data.get("qualification_decision") == "NOT_A_PASS", "controlled rollout validator cannot declare qualification PASS", errors)

    source_sha = data.get("source_sha")
    if final:
        _require(data.get("status") == "CONTROLLED_ROLLOUT_COMPLETE", "final rollout status is not complete", errors)
        _require(_is_sha40(source_sha), "final source_sha must be a full lowercase 40-hex SHA", errors)
        _require(bool(data.get("scope_ref")), "final rollout requires P1 scope reference", errors)
        _require(bool(data.get("authorisation_policy_ref")), "final rollout requires authorisation policy reference", errors)
        _require(bool(data.get("stop_rollback_ref")), "final rollout requires stop/rollback reference", errors)
        _require(bool(data.get("final_evidence_ref")), "final rollout requires final evidence reference", errors)
    else:
        _require(
            data.get("status") in {"PREPARATION_ONLY_NOT_EXECUTED", "CONTROLLED_ROLLOUT_COMPLETE"},
            "unknown rollout status",
            errors,
        )
        if source_sha is not None:
            _require(_is_sha40(source_sha), "source_sha must be null or a full lowercase 40-hex SHA", errors)

    artifacts = data.get("artifact_sha256")
    _require(isinstance(artifacts, list), "artifact_sha256 must be a list", errors)
    if isinstance(artifacts, list):
        if final:
            _require(bool(artifacts), "final rollout requires at least one release artifact SHA-256", errors)
        for index, digest in enumerate(artifacts):
            _require(_is_sha256(digest), f"artifact_sha256[{index}] must be full lowercase SHA-256", errors)

    sessions = data.get("sessions")
    _require(isinstance(sessions, list), "sessions must be a list", errors)
    if isinstance(sessions, list):
        if final:
            _require(bool(sessions), "final rollout requires at least one real authorised session", errors)
        seen_ids: set[str] = set()
        for index, session in enumerate(sessions):
            prefix = f"sessions[{index}]"
            _require(isinstance(session, dict), f"{prefix} must be an object", errors)
            if not isinstance(session, dict):
                continue
            session_id = session.get("session_id")
            _require(isinstance(session_id, str) and bool(session_id), f"{prefix}.session_id is required", errors)
            if isinstance(session_id, str) and session_id:
                _require(session_id not in seen_ids, f"duplicate session_id: {session_id}", errors)
                seen_ids.add(session_id)
            if final:
                _require(session.get("source_sha") == source_sha, f"{prefix} is not bound to final source_sha", errors)
                _require(session.get("authorisation_status") == "VERIFIED", f"{prefix} authorisation is not VERIFIED", errors)
                _require(session.get("observed_by_human") is True, f"{prefix} must be a real human-observed session", errors)
                _require(session.get("synthetic_session") is False, f"{prefix} cannot be synthetic", errors)
                _require(_is_utc(session.get("started_at")), f"{prefix}.started_at must be UTC RFC3339", errors)
                _require(_is_utc(session.get("ended_at")), f"{prefix}.ended_at must be UTC RFC3339", errors)
                _require(bool(session.get("operator_id")), f"{prefix}.operator_id is required", errors)
                _require(bool(session.get("environment_ref")), f"{prefix}.environment_ref is required", errors)
                _require(bool(session.get("workload_ref")), f"{prefix}.workload_ref is required", errors)
                _require(bool(session.get("evidence_ref")), f"{prefix}.evidence_ref is required", errors)
                _require(session.get("operator_attestation") is True, f"{prefix} requires operator/observer attestation", errors)
                session_artifacts = session.get("artifact_sha256")
                _require(isinstance(session_artifacts, list) and bool(session_artifacts), f"{prefix} requires artifact hashes", errors)
                if isinstance(session_artifacts, list):
                    for digest in session_artifacts:
                        _require(digest in artifacts, f"{prefix} references artifact not in final artifact set", errors)

    findings = data.get("findings")
    _require(isinstance(findings, list), "findings must be a list", errors)
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            prefix = f"findings[{index}]"
            _require(isinstance(finding, dict), f"{prefix} must be an object", errors)
            if not isinstance(finding, dict):
                continue
            severity = finding.get("severity")
            status = finding.get("status")
            _require(severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL", "QUALIFICATION_BLOCKER"}, f"{prefix}.severity invalid", errors)
            _require(status in {"OPEN", "REMEDIATED", "ACCEPTED_NON_BLOCKING"}, f"{prefix}.status invalid", errors)
            _require(bool(finding.get("evidence_ref")), f"{prefix}.evidence_ref is required", errors)
            if final and severity in BLOCKING_SEVERITIES:
                _require(status == "REMEDIATED", f"{prefix} blocking finding is not REMEDIATED", errors)
                _require(bool(finding.get("retest_ref")), f"{prefix} blocking finding requires retest_ref", errors)
            if final and status == "ACCEPTED_NON_BLOCKING":
                _require(bool(finding.get("rationale")), f"{prefix} accepted risk requires rationale", errors)
                _require(bool(finding.get("approver_ref")), f"{prefix} accepted risk requires approver_ref", errors)

    blockers = data.get("release_blockers_open")
    _require(isinstance(blockers, list), "release_blockers_open must be a list", errors)
    if final and isinstance(blockers, list):
        _require(not blockers, "final rollout cannot have open release blockers", errors)

    limitations = data.get("limitations")
    _require(isinstance(limitations, list), "limitations must be a list", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("INVALID: root must be an object", file=sys.stderr)
        return 2

    errors = validate(data, final=args.final)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1

    print("VALID_STRUCTURE_NOT_QUALIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
