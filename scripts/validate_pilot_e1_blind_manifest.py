#!/usr/bin/env python3
"""Validate the metadata structure of a ThisTinti E1 blind-run manifest.

This does not authenticate reviewers, authorisations, companies, signatures,
content hashes, or blind-result correctness. It must never be treated as a
qualification PASS by itself.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
HASH64 = re.compile(r"^[0-9a-f]{64}$")


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def validate(doc: dict, final: bool) -> list[str]:
    errors: list[str] = []

    def req(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    req(doc.get("schema") == "thistinti-pilot-e1-blind", "unexpected schema")
    req(doc.get("schema_version") == 1, "schema_version must be 1")
    req(doc.get("claim") == "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1", "unexpected claim")
    req(doc.get("release_version") == "1.0.0", "release_version must be 1.0.0")
    req(doc.get("release_tag") == "v1.0.0", "release_tag must be v1.0.0")

    if not final:
        req(doc.get("status") == "PREPARATION_ONLY_NOT_EXECUTED", "preparation template must remain PREPARATION_ONLY_NOT_EXECUTED")
        req(doc.get("result") == "GAP", "preparation template result must remain GAP")
        return errors

    req(doc.get("status") == "EXECUTED", "final manifest status must be EXECUTED")
    req(isinstance(doc.get("candidate_sha"), str) and bool(SHA40.fullmatch(doc["candidate_sha"])), "candidate_sha must be full 40-hex")

    try:
        frozen_at = _time(doc.get("frozen_at"), "frozen_at")
    except ValueError as exc:
        errors.append(str(exc))
        frozen_at = None

    components = doc.get("components") if isinstance(doc.get("components"), dict) else {}
    for key in (
        "rule_pack_id", "rule_pack_hash", "practice_model_id", "practice_model_hash",
        "company_profile_id", "company_profile_hash", "provenance_configuration_hash",
        "qualification_configuration_hash",
    ):
        req(isinstance(components.get(key), str) and bool(components.get(key)), f"components.{key} is required")
    req(isinstance(components.get("parser_versions"), list) and len(components.get("parser_versions", [])) > 0, "components.parser_versions must be non-empty")

    pool = doc.get("blind_pool") if isinstance(doc.get("blind_pool"), list) else []
    req(20 <= len(pool) <= 25, "blind_pool must contain 20-25 cases")
    ids: list[str] = []
    hashes: list[str] = []
    for index, case in enumerate(pool):
        if not isinstance(case, dict):
            errors.append(f"blind_pool[{index}] must be an object")
            continue
        case_id = case.get("case_id")
        content_hash = case.get("content_sha256")
        req(isinstance(case_id, str) and bool(case_id), f"blind_pool[{index}].case_id is required")
        req(isinstance(content_hash, str) and bool(HASH64.fullmatch(content_hash)), f"blind_pool[{index}].content_sha256 must be 64-hex")
        req(case.get("authorization_status") == "VERIFIED", f"blind_pool[{index}] authorization must be VERIFIED")
        req(case.get("anonymization_status") == "VERIFIED", f"blind_pool[{index}] anonymization must be VERIFIED")
        req(case.get("pool") == "BLIND", f"blind_pool[{index}] pool must be BLIND")
        req(case.get("pre_freeze_content_exposure") is False, f"blind_pool[{index}] pre-freeze exposure is contamination")
        if isinstance(case_id, str):
            ids.append(case_id)
        if isinstance(content_hash, str):
            hashes.append(content_hash)
    req(len(ids) == len(set(ids)), "duplicate blind case_id")
    req(len(hashes) == len(set(hashes)), "duplicate blind content hash")

    reviewers = doc.get("reviewers") if isinstance(doc.get("reviewers"), dict) else {}
    a = reviewers.get("reviewer_a_id")
    b = reviewers.get("reviewer_b_id")
    req(isinstance(a, str) and bool(a), "reviewer_a_id is required")
    req(isinstance(b, str) and bool(b), "reviewer_b_id is required")
    req(a != b, "reviewers must be distinct")
    try:
        a_sealed = _time(reviewers.get("reference_a_sealed_at"), "reference_a_sealed_at")
        b_sealed = _time(reviewers.get("reference_b_sealed_at"), "reference_b_sealed_at")
        exposed = _time(reviewers.get("findings_exposed_at"), "findings_exposed_at")
        req(a_sealed < exposed and b_sealed < exposed, "both reviewer references must be sealed before findings exposure")
        if frozen_at is not None:
            req(frozen_at <= exposed, "findings exposure cannot precede freeze")
    except ValueError as exc:
        errors.append(str(exc))

    adjudication = doc.get("adjudication") if isinstance(doc.get("adjudication"), dict) else {}
    req(isinstance(adjudication.get("adjudicator_id"), str) and bool(adjudication.get("adjudicator_id")), "adjudicator_id is required")
    req(adjudication.get("preserves_original_reviewer_records") is True, "adjudication must preserve original reviewer records")
    try:
        _time(adjudication.get("performed_at"), "adjudication.performed_at")
    except ValueError as exc:
        errors.append(str(exc))

    execution = doc.get("execution") if isinstance(doc.get("execution"), dict) else {}
    req(execution.get("tuning_during_run") is False, "tuning during blind run is prohibited")
    req(execution.get("protocol_contamination") is False, "protocol contamination blocks final validation")
    req(execution.get("material_change_after_freeze") is False, "material post-freeze change requires a new candidate/holdout path")
    try:
        start = _time(execution.get("started_at"), "execution.started_at")
        end = _time(execution.get("ended_at"), "execution.ended_at")
        req(start <= end, "execution ended_at must not precede started_at")
        if frozen_at is not None:
            req(frozen_at <= start, "execution cannot start before freeze")
    except ValueError as exc:
        errors.append(str(exc))

    econ = doc.get("economic_reporting") if isinstance(doc.get("economic_reporting"), dict) else {}
    company_value = econ.get("company_validated_recoverable_or_avoided_value")
    if company_value not in (None, 0, 0.0):
        req(econ.get("company_validation_record_present") is True, "company-validated value requires a distinct company validation record")

    req(doc.get("result") in {"PASS", "FAIL"}, "final result must be PASS or FAIL")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true", help="apply final-run fail-closed checks")
    args = parser.parse_args()

    try:
        doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict):
        print("INVALID: manifest root must be an object", file=sys.stderr)
        return 2

    errors = validate(doc, args.final)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1

    if args.final:
        print("VALID_STRUCTURE_NOT_QUALIFICATION_PASS")
    else:
        print("VALID_PREPARATION_ONLY_NOT_EXECUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
