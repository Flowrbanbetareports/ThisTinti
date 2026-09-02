#!/usr/bin/env python3
"""Validate ThisTinti Qualified human-campaign evidence structure.

This validator checks internal structural invariants only. It cannot establish that a
human observation occurred, that a participant was independent, or that accessibility
or usability requirements are substantively satisfied.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ISSUE94_CRITERIA = {
    "installation_first_run",
    "workspace_navigation",
    "demo_worker_path",
    "finding_evidence_original_trace",
    "correction_reanalysis",
    "activity_retry_restart_persistence",
    "diagnostics_json",
    "claims_observation",
    "update_backup_restore_uninstall",
    "zoom_125_150_200",
    "keyboard_only_human",
    "assistive_technology_human",
    "serious_defect_reproduction",
}
ALLOWED_CRITERION_RESULTS = {"PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE"}
BLOCKING_IMPACTS = {"BLOCKER"}


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate(data: dict, final: bool = False) -> list[str]:
    errors: list[str] = []

    if data.get("schema") != "thistinti-human-campaign-v1":
        _fail(errors, "unexpected schema")

    candidate = data.get("candidate")
    if not isinstance(candidate, dict):
        return errors + ["candidate must be an object"]

    if not final:
        if data.get("state") != "PREPARATION_ONLY_NOT_EXECUTED":
            _fail(errors, "preparation template must remain PREPARATION_ONLY_NOT_EXECUTED")
        if data.get("final_result") != "NOT_A_PASS":
            _fail(errors, "preparation template must remain NOT_A_PASS")
        return errors

    if data.get("state") != "EXECUTED":
        _fail(errors, "final evidence state must be EXECUTED")
    if not SHA40.fullmatch(str(candidate.get("source_sha") or "")):
        _fail(errors, "candidate.source_sha must be full lowercase 40-hex")
    if candidate.get("release_version") != "1.0.0":
        _fail(errors, "candidate.release_version must be 1.0.0")
    if not candidate.get("artifact_id"):
        _fail(errors, "candidate.artifact_id is required")
    if not SHA256.fullmatch(str(candidate.get("artifact_sha256") or "")):
        _fail(errors, "candidate.artifact_sha256 must be lowercase 64-hex")
    if not candidate.get("environment"):
        _fail(errors, "candidate.environment is required")

    sessions = data.get("sessions")
    if not isinstance(sessions, list):
        _fail(errors, "sessions must be a list")
        sessions = []

    untrained = [s for s in sessions if s.get("prior_this_tinti_experience") == "NONE"]
    if len(untrained) != 10:
        _fail(errors, "final #32 evidence requires exactly 10 untrained sessions")

    session_ids = [s.get("session_id") for s in sessions]
    if any(not sid for sid in session_ids) or len(session_ids) != len(set(session_ids)):
        _fail(errors, "session_id values must be present and unique")

    success_count = 0
    for session in untrained:
        required = (
            session.get("purpose_explained_correctly") is True,
            session.get("reached_first_evidence_backed_item") is True,
            session.get("within_protocol_target") is True,
            session.get("blocking_assistance") is False,
            session.get("serious_interpretation_failure") is False,
        )
        if all(required):
            success_count += 1
        if not session.get("observer_id"):
            _fail(errors, f"session {session.get('session_id')} missing observer_id")
        if not session.get("evidence_refs"):
            _fail(errors, f"session {session.get('session_id')} missing evidence_refs")

    issue32 = data.get("issue_32", {})
    if issue32.get("untrained_session_target") != 10:
        _fail(errors, "issue_32.untrained_session_target must remain 10")
    if issue32.get("minimum_successes") != 8:
        _fail(errors, "issue_32.minimum_successes must remain 8")
    if issue32.get("successes") != success_count:
        _fail(errors, "issue_32.successes does not match session-derived successes")
    if success_count < 8 or issue32.get("result") != "PASS":
        _fail(errors, "#32 final structure requires >=8/10 successes and result PASS")

    observations = data.get("observations")
    if not isinstance(observations, list):
        _fail(errors, "observations must be a list")
        observations = []

    human_keyboard = False
    human_at = False
    known_sessions = set(session_ids)
    passed_observation_criteria: set[str] = set()
    for obs in observations:
        if obs.get("session_id") not in known_sessions:
            _fail(errors, f"observation {obs.get('observation_id')} references unknown session")
        if not obs.get("evidence_refs"):
            _fail(errors, f"observation {obs.get('observation_id')} missing evidence_refs")
        criterion = obs.get("issue_94_criterion")
        if criterion not in ISSUE94_CRITERIA:
            _fail(errors, f"observation {obs.get('observation_id')} has invalid #94 criterion")
            continue
        if obs.get("result") == "PASS":
            passed_observation_criteria.add(criterion)
        if criterion == "keyboard_only_human" and obs.get("result") == "PASS":
            human_keyboard = human_keyboard or obs.get("observation_mode") == "HUMAN"
        if criterion == "assistive_technology_human" and obs.get("result") == "PASS":
            human_at = human_at or (
                obs.get("observation_mode") == "HUMAN"
                and bool(obs.get("assistive_technology"))
            )

    if not human_keyboard:
        _fail(errors, "keyboard-only PASS requires a HUMAN observation")
    if not human_at:
        _fail(errors, "assistive-technology PASS requires HUMAN observation and tool/version")

    issue94 = data.get("issue_94", {})
    criteria = issue94.get("criteria")
    if not isinstance(criteria, dict) or set(criteria) != ISSUE94_CRITERIA:
        _fail(errors, "issue_94.criteria must contain the exact required criterion set")
        criteria = criteria if isinstance(criteria, dict) else {}
    rationales = issue94.get("not_applicable_rationales", {})
    for name in ISSUE94_CRITERIA:
        result = criteria.get(name)
        if result not in ALLOWED_CRITERION_RESULTS:
            _fail(errors, f"invalid result for #94 criterion {name}")
        if result == "NOT_RUN" or result == "FAIL":
            _fail(errors, f"#94 criterion {name} is not complete")
        if result == "NOT_APPLICABLE" and not rationales.get(name):
            _fail(errors, f"#94 criterion {name} needs NOT_APPLICABLE rationale")
        if result == "PASS" and name not in passed_observation_criteria:
            _fail(errors, f"#94 criterion {name} lacks a supporting PASS observation")
    if issue94.get("result") != "PASS":
        _fail(errors, "issue_94.result must be PASS for final structural validation")

    findings = data.get("findings")
    if not isinstance(findings, list):
        _fail(errors, "findings must be a list")
        findings = []
    for finding in findings:
        if (
            finding.get("qualification_impact") in BLOCKING_IMPACTS
            and finding.get("status") not in {"RETESTED_PASS", "REJECTED_NOT_APPLICABLE"}
        ):
            _fail(errors, f"open blocking finding: {finding.get('finding_id')}")

    if data.get("final_result") != "PASS":
        _fail(errors, "final_result must be PASS only after all structural gates are complete")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate(data, final=args.final)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("human campaign manifest structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
