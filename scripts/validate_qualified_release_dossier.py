#!/usr/bin/env python3
"""Fail-closed structural validator for the ThisTinti 1.0 Qualified evidence dossier.

This validator checks release identity, exact-SHA binding and completion metadata. It does
not authenticate external evidence and does not declare the product qualified.
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

EXPECTED_SCHEMA = "thistinti-qualified-release-dossier"
EXPECTED_SCHEMA_VERSION = 3
EXPECTED_MAIN_POST_MERGE_CHECKS = {"P1 PostgreSQL Concurrency Evidence"}
EXPECTED_P1_RULE_COUNT = 6
EXPECTED_CONCURRENCY_SCENARIOS = {"concurrent_judgment", "conflicting_judgment"}
EXPECTED_TRACKS = {
    "stream_a_technical",
    "stream_b_e1",
    "security_134",
    "privacy_legal_135",
    "windows_signing_20",
    "human_32_94",
    "performance_166",
    "data_protection_167",
    "recovery_portability_168",
    "residual_risk_21",
    "controlled_rollout",
}
ALLOWED_TRACK_STATUS = {"WAITING_FINAL_SHA", "WAITING_EXTERNAL", "BLOCKED", "COMPLETE"}


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _is_sha40(value: Any) -> bool:
    return isinstance(value, str) and SHA40.fullmatch(value) is not None


def _validate_semantic_concurrency_proof(
    proof: Any,
    source_sha: Any,
    final: bool,
    errors: list[str],
) -> None:
    _require(isinstance(proof, dict), "semantic_concurrency_proof must be an object", errors)
    if not isinstance(proof, dict):
        return

    _require(
        proof.get("expected_rule_count") == EXPECTED_P1_RULE_COUNT,
        f"semantic_concurrency_proof.expected_rule_count must be {EXPECTED_P1_RULE_COUNT}",
        errors,
    )
    rules = proof.get("rules")
    _require(isinstance(rules, list), "semantic_concurrency_proof.rules must be a list", errors)
    if final:
        _require(bool(proof.get("scope_ref")), "final semantic concurrency proof requires scope_ref", errors)
    if not isinstance(rules, list):
        return

    if final:
        _require(
            len(rules) == EXPECTED_P1_RULE_COUNT,
            f"final semantic concurrency proof must contain exactly {EXPECTED_P1_RULE_COUNT} P1 rules",
            errors,
        )

    seen_rule_ids: set[str] = set()
    for index, rule in enumerate(rules):
        prefix = f"semantic_concurrency_proof.rules[{index}]"
        _require(isinstance(rule, dict), f"{prefix} must be an object", errors)
        if not isinstance(rule, dict):
            continue

        rule_id = rule.get("rule_id")
        _require(isinstance(rule_id, str) and bool(rule_id), f"{prefix}.rule_id is required", errors)
        if isinstance(rule_id, str) and rule_id:
            _require(rule_id not in seen_rule_ids, f"duplicate semantic concurrency rule_id: {rule_id}", errors)
            seen_rule_ids.add(rule_id)

        rule_sha = rule.get("source_sha")
        if rule_sha is not None:
            _require(_is_sha40(rule_sha), f"{prefix}.source_sha must be full 40-hex", errors)
        if final:
            _require(rule_sha == source_sha, f"{prefix} is not bound to final source_sha", errors)

        scenarios = rule.get("scenarios")
        _require(isinstance(scenarios, dict), f"{prefix}.scenarios must be an object", errors)
        if not isinstance(scenarios, dict):
            continue
        _require(
            set(scenarios) == EXPECTED_CONCURRENCY_SCENARIOS,
            f"{prefix}.scenarios must contain exactly concurrent_judgment and conflicting_judgment",
            errors,
        )

        for scenario_name in sorted(EXPECTED_CONCURRENCY_SCENARIOS):
            scenario = scenarios.get(scenario_name)
            scenario_prefix = f"{prefix}.scenarios.{scenario_name}"
            _require(isinstance(scenario, dict), f"{scenario_prefix} must be an object", errors)
            if not isinstance(scenario, dict):
                continue
            if final:
                _require(
                    scenario.get("status") == "PROVEN_FAIL_CLOSED",
                    f"{scenario_prefix}.status must be PROVEN_FAIL_CLOSED",
                    errors,
                )
                _require(
                    scenario.get("production_decision_exercised") is True,
                    f"{scenario_prefix} did not exercise the production decision path",
                    errors,
                )
                _require(
                    scenario.get("review_decision_persisted") is True,
                    f"{scenario_prefix} did not persist ReviewDecision",
                    errors,
                )
                _require(
                    scenario.get("provenance_judgment_persisted") is True,
                    f"{scenario_prefix} did not persist ProvenanceJudgment",
                    errors,
                )
                refs = scenario.get("evidence_refs")
                _require(
                    isinstance(refs, list) and bool(refs),
                    f"{scenario_prefix} has no evidence_refs",
                    errors,
                )


def validate(data: dict[str, Any], final: bool = False) -> list[str]:
    errors: list[str] = []

    _require(data.get("schema") == EXPECTED_SCHEMA, "invalid schema", errors)
    _require(
        data.get("schema_version") == EXPECTED_SCHEMA_VERSION,
        f"schema_version must be {EXPECTED_SCHEMA_VERSION}",
        errors,
    )
    _require(data.get("release_version") == "1.0.0", "release_version must be exactly 1.0.0", errors)
    _require(data.get("release_tag") == "v1.0.0", "release_tag must be exactly v1.0.0", errors)

    source_sha = data.get("source_sha")
    if final:
        _require(data.get("status") == "FINAL_CANDIDATE_EVIDENCE_COMPLETE", "final status is not complete", errors)
        _require(_is_sha40(source_sha), "final source_sha must be a full lowercase 40-hex SHA", errors)
    else:
        _require(
            data.get("status") in {"PREPARATION_ONLY_NOT_EXECUTED", "FINAL_CANDIDATE_EVIDENCE_COMPLETE"},
            "unknown dossier status",
            errors,
        )
        if source_sha is not None:
            _require(_is_sha40(source_sha), "source_sha must be null or a full lowercase 40-hex SHA", errors)

    policy = data.get("required_check_policy")
    _require(isinstance(policy, dict), "required_check_policy must be an object", errors)
    if isinstance(policy, dict):
        checks = policy.get("checks")
        main_post_merge_checks = policy.get("main_post_merge_checks")
        _require(isinstance(checks, list), "required_check_policy.checks must be a list", errors)
        _require(
            isinstance(main_post_merge_checks, list),
            "required_check_policy.main_post_merge_checks must be a list",
            errors,
        )
        _validate_semantic_concurrency_proof(
            policy.get("semantic_concurrency_proof"), source_sha, final, errors
        )
        if final:
            _require(bool(policy.get("reference")), "final dossier requires a required-check policy reference", errors)
            _require(bool(policy.get("captured_at")), "final dossier requires required-check capture time", errors)
            _require(bool(checks), "final dossier requires at least one required workflow check", errors)
        if isinstance(checks, list):
            for index, check in enumerate(checks):
                prefix = f"required_check_policy.checks[{index}]"
                _require(isinstance(check, dict), f"{prefix} must be an object", errors)
                if not isinstance(check, dict):
                    continue
                _require(bool(check.get("name")), f"{prefix}.name is required", errors)
                if final:
                    _require(check.get("source_sha") == source_sha, f"{prefix} is not bound to final source_sha", errors)
                    _require(check.get("conclusion") == "success", f"{prefix} did not conclude success", errors)
                    _require(bool(check.get("evidence_ref")), f"{prefix}.evidence_ref is required", errors)
        if isinstance(main_post_merge_checks, list):
            names: list[str] = []
            for index, check in enumerate(main_post_merge_checks):
                prefix = f"required_check_policy.main_post_merge_checks[{index}]"
                _require(isinstance(check, dict), f"{prefix} must be an object", errors)
                if not isinstance(check, dict):
                    continue
                name = check.get("name")
                _require(isinstance(name, str) and bool(name), f"{prefix}.name is required", errors)
                if isinstance(name, str) and name:
                    names.append(name)
                if final:
                    _require(check.get("source_sha") == source_sha, f"{prefix} is not bound to final source_sha", errors)
                    _require(check.get("branch") == "main", f"{prefix} must be recorded from branch main", errors)
                    _require(check.get("event") == "push", f"{prefix} must be recorded from a push run", errors)
                    _require(check.get("conclusion") == "success", f"{prefix} did not conclude success", errors)
                    _require(bool(check.get("evidence_ref")), f"{prefix}.evidence_ref is required", errors)
            if final:
                _require(
                    set(names) == EXPECTED_MAIN_POST_MERGE_CHECKS and len(names) == len(EXPECTED_MAIN_POST_MERGE_CHECKS),
                    "main_post_merge_checks must contain exactly the required exact-main check set",
                    errors,
                )

    artifacts = data.get("release_artifacts")
    _require(isinstance(artifacts, list), "release_artifacts must be a list", errors)
    if isinstance(artifacts, list):
        if final:
            _require(bool(artifacts), "final dossier requires release artifacts", errors)
        seen_names: set[str] = set()
        for index, artifact in enumerate(artifacts):
            prefix = f"release_artifacts[{index}]"
            _require(isinstance(artifact, dict), f"{prefix} must be an object", errors)
            if not isinstance(artifact, dict):
                continue
            name = artifact.get("name")
            _require(isinstance(name, str) and bool(name), f"{prefix}.name is required", errors)
            if isinstance(name, str) and name:
                _require(name not in seen_names, f"duplicate release artifact name: {name}", errors)
                seen_names.add(name)
            if final:
                _require(artifact.get("source_sha") == source_sha, f"{prefix} is not bound to final source_sha", errors)
                digest = artifact.get("sha256")
                _require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None, f"{prefix}.sha256 invalid", errors)
                _require(bool(artifact.get("evidence_ref")), f"{prefix}.evidence_ref is required", errors)

    tracks = data.get("tracks")
    _require(isinstance(tracks, dict), "tracks must be an object", errors)
    if isinstance(tracks, dict):
        _require(set(tracks) == EXPECTED_TRACKS, "tracks must match the required qualification track set exactly", errors)
        for name in sorted(EXPECTED_TRACKS):
            track = tracks.get(name)
            _require(isinstance(track, dict), f"track {name} must be an object", errors)
            if not isinstance(track, dict):
                continue
            status = track.get("status")
            _require(status in ALLOWED_TRACK_STATUS, f"track {name} has invalid status", errors)
            refs = track.get("evidence_refs")
            _require(isinstance(refs, list), f"track {name}.evidence_refs must be a list", errors)
            track_sha = track.get("source_sha")
            if track_sha is not None:
                _require(_is_sha40(track_sha), f"track {name}.source_sha must be full 40-hex", errors)
            if final:
                _require(status == "COMPLETE", f"track {name} is not COMPLETE", errors)
                _require(track_sha == source_sha, f"track {name} is not bound to final source_sha", errors)
                _require(bool(refs), f"track {name} has no evidence_refs", errors)

    change = data.get("change_control")
    _require(isinstance(change, dict), "change_control must be an object", errors)
    if isinstance(change, dict) and final:
        _require(
            change.get("material_change_since_completed_evidence") is False,
            "material change exists or has not been resolved by fresh evidence",
            errors,
        )
        holdout_required = change.get("holdout_required")
        _require(isinstance(holdout_required, bool), "holdout_required must be boolean in final dossier", errors)
        if holdout_required is True:
            _require(change.get("holdout_status") == "COMPLETE", "required holdout is not COMPLETE", errors)
            refs = change.get("holdout_evidence_refs")
            _require(isinstance(refs, list) and bool(refs), "required holdout has no evidence refs", errors)
        elif holdout_required is False:
            _require(
                change.get("holdout_status") in {"NOT_REQUIRED", "COMPLETE"},
                "holdout_status must explain why no holdout is pending",
                errors,
            )

    limitations = data.get("limitations")
    _require(isinstance(limitations, list), "limitations must be a list", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dossier", type=Path)
    parser.add_argument("--final", action="store_true", help="require a structurally complete final-candidate dossier")
    args = parser.parse_args()

    try:
        raw = args.dossier.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("INVALID: dossier root must be a JSON object", file=sys.stderr)
        return 2

    errors = validate(data, final=args.final)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1

    if args.final:
        print("VALID_STRUCTURE_NOT_QUALIFICATION_PASS")
    else:
        print("VALID_PREPARATION_STRUCTURE_NOT_QUALIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
