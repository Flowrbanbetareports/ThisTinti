#!/usr/bin/env python3
"""Fail-closed structural validator for independent external-review evidence.

A successful validation means only that the register is structurally complete and
contains no blocker declared by the supplied evidence. It does not authenticate
reviewers or substitute for independent assessment.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "NOT_APPLICABLE"}
ALLOWED_MATERIALITY = {"MATERIAL", "NON_MATERIAL", "UNKNOWN", "NOT_APPLICABLE"}
ALLOWED_REMEDIATION = {"OPEN", "IN_PROGRESS", "REMEDIATED", "NOT_APPLICABLE", "RISK_ACCEPTED"}
ALLOWED_RETEST = {"NOT_REQUIRED", "NOT_RUN", "PASS", "FAIL"}
TRACKS = {"SECURITY": 134, "PRIVACY_LEGAL": 135}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_finding(track_name: str, finding: object, errors: list[str]) -> None:
    if not isinstance(finding, dict):
        fail(errors, f"{track_name}: finding must be an object")
        return

    prefix = f"{track_name}/{finding.get('id', '<missing-id>')}"
    for key in ("id", "title", "description", "surface", "remediation_status"):
        if not nonempty(finding.get(key)):
            fail(errors, f"{prefix}: missing {key}")

    severity = finding.get("severity")
    materiality = finding.get("materiality")
    remediation = finding.get("remediation_status")
    retest_required = finding.get("retest_required")
    retest_status = finding.get("retest_status")

    if severity not in ALLOWED_SEVERITIES:
        fail(errors, f"{prefix}: invalid severity")
    if materiality not in ALLOWED_MATERIALITY:
        fail(errors, f"{prefix}: invalid materiality")
    if remediation not in ALLOWED_REMEDIATION:
        fail(errors, f"{prefix}: invalid remediation_status")
    if not isinstance(retest_required, bool):
        fail(errors, f"{prefix}: retest_required must be boolean")
    if retest_status not in ALLOWED_RETEST:
        fail(errors, f"{prefix}: invalid retest_status")

    if remediation == "REMEDIATED" and not (
        nonempty(finding.get("remediation_reference")) or nonempty(finding.get("remediation_sha"))
    ):
        fail(errors, f"{prefix}: remediated finding needs remediation reference or SHA")

    remediation_sha = finding.get("remediation_sha")
    if remediation_sha is not None and not (isinstance(remediation_sha, str) and SHA40.fullmatch(remediation_sha)):
        fail(errors, f"{prefix}: remediation_sha must be full 40-hex SHA")

    if retest_required and retest_status != "PASS":
        fail(errors, f"{prefix}: required retest has not passed")
    if not retest_required and retest_status not in {"NOT_REQUIRED", "PASS"}:
        fail(errors, f"{prefix}: inconsistent retest status")

    if severity in {"CRITICAL", "HIGH"} and remediation in {"OPEN", "IN_PROGRESS"}:
        fail(errors, f"{prefix}: unresolved release-blocking security severity")
    if track_name == "PRIVACY_LEGAL" and materiality == "MATERIAL" and remediation in {"OPEN", "IN_PROGRESS"}:
        fail(errors, f"{prefix}: unresolved material privacy/legal finding")

    if remediation == "RISK_ACCEPTED":
        acceptance = finding.get("risk_acceptance")
        if not isinstance(acceptance, dict):
            fail(errors, f"{prefix}: risk acceptance record required")
        else:
            for key in ("rationale", "approver", "accepted_at", "review_trigger"):
                if not nonempty(acceptance.get(key)):
                    fail(errors, f"{prefix}: risk acceptance missing {key}")


def validate(data: object, final: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["register must be a JSON object"]

    if data.get("schema") != "thistinti-external-review-findings" or data.get("schema_version") != 1:
        fail(errors, "unsupported schema")

    if data.get("release_version") != "1.0.0":
        fail(errors, "release_version must be exactly 1.0.0")
    if data.get("release_tag") != "v1.0.0":
        fail(errors, "release_tag must be exactly v1.0.0; legacy prerelease tags are not valid")

    candidate_sha = data.get("candidate_sha")
    if final and not (isinstance(candidate_sha, str) and SHA40.fullmatch(candidate_sha)):
        fail(errors, "final register requires full 40-hex candidate_sha")
    if final and not nonempty(data.get("environment")):
        fail(errors, "final register requires environment")

    tracks = data.get("tracks")
    if not isinstance(tracks, dict):
        fail(errors, "tracks must be an object")
        return errors

    if set(tracks) != set(TRACKS):
        fail(errors, "tracks must contain exactly SECURITY and PRIVACY_LEGAL")

    for track_name, issue_number in TRACKS.items():
        track = tracks.get(track_name)
        if not isinstance(track, dict):
            fail(errors, f"{track_name}: track missing")
            continue
        if track.get("issue") != issue_number:
            fail(errors, f"{track_name}: wrong issue binding")
        if final:
            for key in ("independent_reviewer", "reviewer_organisation", "report_date", "report_reference"):
                if not nonempty(track.get(key)):
                    fail(errors, f"{track_name}: final evidence missing {key}")
            scope = track.get("scope")
            if not isinstance(scope, list) or not scope or not all(nonempty(item) for item in scope):
                fail(errors, f"{track_name}: final evidence requires non-empty scope")
        findings = track.get("findings")
        if not isinstance(findings, list):
            fail(errors, f"{track_name}: findings must be a list")
        else:
            seen: set[str] = set()
            for finding in findings:
                validate_finding(track_name, finding, errors)
                if isinstance(finding, dict) and nonempty(finding.get("id")):
                    finding_id = finding["id"]
                    if finding_id in seen:
                        fail(errors, f"{track_name}: duplicate finding id {finding_id}")
                    seen.add(finding_id)

    if final:
        if data.get("status") != "EXTERNAL_REVIEWS_COMPLETE":
            fail(errors, "final status must be EXTERNAL_REVIEWS_COMPLETE")
        if data.get("final_disposition") != "PASS":
            fail(errors, "final_disposition must be PASS")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("register", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    try:
        data = json.loads(args.register.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    errors = validate(data, args.final)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print("VALID STRUCTURE — not proof of independent review authenticity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
