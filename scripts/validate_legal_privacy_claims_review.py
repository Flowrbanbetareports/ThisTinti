#!/usr/bin/env python3
"""Fail-closed structural validator for the independent #135 review package.

This tool validates completeness and exact-candidate binding only. It cannot
authenticate a reviewer, provide legal advice, approve claims, or establish a
qualification PASS.
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
DATE_OR_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z)?$")

EXPECTED_SCHEMA = "thistinti-legal-privacy-claims-review"
BOUNDED_CLAIM = "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1"
ALLOWED_DISPOSITIONS = {
    "APPROVED",
    "APPROVED_WITH_LIMITATION",
    "REMEDIATION_REQUIRED",
    "OUT_OF_SCOPE_WITH_REASON",
    "NOT_REVIEWED",
}
EXPECTED_AREAS = {
    "controller_processor_roles",
    "lawful_basis_purpose_limitation",
    "pilot_authorisation",
    "anonymisation_pseudonymisation",
    "canonical_evidence_snapshots",
    "snapshot_retention_deletion",
    "snapshot_backup_restore",
    "snapshot_encryption_storage_boundary",
    "reviewer_export_disclosure",
    "calibration_blind_holdout_governance",
    "retention_deletion_export",
    "backup_recovery",
    "dpa_subprocessors",
    "data_subject_incident_handling",
    "local_first_deployment_claims",
    "licence_notices",
    "terms_disclaimer_support_warranty",
    "design_partner_contracts",
    "thistinti_name_trademark",
    "qualified_claim",
    "accuracy_compliance_autonomy_claims",
    "economic_claims",
    "public_materials_consistency",
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(_nonempty(item) for item in value)


def _validate_inventory(items: Any, final: bool, errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append("material_inventory must be a list")
        return
    if final and not items:
        errors.append("final review requires non-empty material_inventory")

    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"material_inventory[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        for key in ("id", "reference", "version_or_source_sha", "reviewed_at"):
            if not _nonempty(item.get(key)):
                errors.append(f"{prefix}: missing {key}")
        if _nonempty(item_id):
            if item_id in seen:
                errors.append(f"{prefix}: duplicate id {item_id}")
            seen.add(item_id)
        reviewed_at = item.get("reviewed_at")
        if _nonempty(reviewed_at) and DATE_OR_UTC.fullmatch(reviewed_at) is None:
            errors.append(f"{prefix}: reviewed_at must be YYYY-MM-DD or UTC RFC3339")
        digest = item.get("sha256")
        fallback = item.get("hash_unavailable_reason")
        if digest is not None:
            if not (isinstance(digest, str) and SHA256.fullmatch(digest)):
                errors.append(f"{prefix}: sha256 must be 64 lowercase hex")
        elif final and not _nonempty(fallback):
            errors.append(f"{prefix}: final inventory item requires sha256 or hash_unavailable_reason")


def validate(data: Any, final: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["review package must be a JSON object"]

    _require(data.get("schema") == EXPECTED_SCHEMA, "invalid schema", errors)
    _require(data.get("schema_version") == 1, "schema_version must be 1", errors)
    _require(data.get("release_version") == "1.0.0", "release_version must be exactly 1.0.0", errors)
    _require(
        data.get("release_tag") == "v1.0.0",
        "release_tag must be exactly v1.0.0; legacy prerelease tags are not valid",
        errors,
    )
    _require(data.get("release_claim") == BOUNDED_CLAIM, "release_claim must remain bounded to P1/E1", errors)
    _require(
        data.get("qualification_decision") == "NOT_A_PASS",
        "this validator cannot declare qualification PASS",
        errors,
    )

    candidate_sha = data.get("candidate_sha")
    if final:
        _require(data.get("status") == "INDEPENDENT_REVIEW_COMPLETE", "final status must be INDEPENDENT_REVIEW_COMPLETE", errors)
        _require(
            isinstance(candidate_sha, str) and SHA40.fullmatch(candidate_sha) is not None,
            "final review requires full 40-hex candidate_sha",
            errors,
        )

    reviewer = data.get("reviewer")
    if not isinstance(reviewer, dict):
        errors.append("reviewer must be an object")
    elif final:
        for key in (
            "name_or_identifier",
            "organisation",
            "independence_statement",
            "competence_scope",
            "review_date",
            "report_reference",
        ):
            if not _nonempty(reviewer.get(key)):
                errors.append(f"final reviewer evidence missing {key}")
        review_date = reviewer.get("review_date")
        if _nonempty(review_date) and DATE_OR_UTC.fullmatch(review_date) is None:
            errors.append("review_date must be YYYY-MM-DD or UTC RFC3339")

    _validate_inventory(data.get("material_inventory"), final, errors)

    matrix = data.get("review_matrix")
    if not isinstance(matrix, dict):
        errors.append("review_matrix must be an object")
    else:
        actual = set(matrix)
        missing = sorted(EXPECTED_AREAS - actual)
        extra = sorted(actual - EXPECTED_AREAS)
        if missing:
            errors.append("review_matrix missing areas: " + ", ".join(missing))
        if extra:
            errors.append("review_matrix has unexpected areas: " + ", ".join(extra))

        for area in sorted(EXPECTED_AREAS & actual):
            row = matrix.get(area)
            if not isinstance(row, dict):
                errors.append(f"{area}: row must be an object")
                continue
            disposition = row.get("disposition")
            if disposition not in ALLOWED_DISPOSITIONS:
                errors.append(f"{area}: invalid disposition")
                continue
            refs = row.get("evidence_refs")
            limitations = row.get("limitations")
            if not _string_list(refs):
                errors.append(f"{area}: evidence_refs must be a list of non-empty strings")
            if not _string_list(limitations):
                errors.append(f"{area}: limitations must be a list of non-empty strings")
            if final and (not isinstance(refs, list) or not refs):
                errors.append(f"{area}: final disposition requires evidence_refs")
            if final and disposition in {"NOT_REVIEWED", "REMEDIATION_REQUIRED"}:
                errors.append(f"{area}: final package cannot contain {disposition}")
            if disposition in {"APPROVED_WITH_LIMITATION", "OUT_OF_SCOPE_WITH_REASON"} and (
                not isinstance(limitations, list) or not limitations
            ):
                errors.append(f"{area}: {disposition} requires explicit limitation/reason")

    if not _string_list(data.get("required_limitations")):
        errors.append("required_limitations must be a list of non-empty strings")
    if not _string_list(data.get("not_reviewed")):
        errors.append("not_reviewed must be a list of non-empty strings")

    if final:
        _require(not data.get("not_reviewed"), "final review cannot retain not_reviewed items", errors)
        _require(_nonempty(data.get("findings_register_ref")), "final review requires findings_register_ref", errors)
        wording = data.get("approved_qualified_wording")
        _require(_nonempty(wording), "final review requires approved_qualified_wording", errors)
        if _nonempty(wording):
            _require(BOUNDED_CLAIM in wording, "approved wording must preserve the bounded P1/E1 Qualified claim", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review_package", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    try:
        data = json.loads(args.review_package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    errors = validate(data, args.final)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1

    print("VALID_STRUCTURE_NOT_QUALIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
