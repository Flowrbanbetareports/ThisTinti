#!/usr/bin/env python3
"""Validate P1/E1 registry and reviewer-protocol preparation without reading case contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
POOLS = {"CALIBRATION", "BLIND", "HOLDOUT"}
AUTH_OK = {"verified"}
ANON_OK = {"not_required_verified", "completed_verified"}
CONTENT_ACCESS = {"none", "metadata_only", "content"}


class ValidationError(ValueError):
    pass


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"{path} must contain a JSON object")
    return data


def _sha256(value: str, field: str) -> None:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ValidationError(f"{field} must be lowercase 64-hex SHA-256")


def validate_registry(data: dict, *, sealed: bool) -> None:
    if data.get("schema") != "thistinti-p1-e1-case-registry" or data.get("schema_version") != 1:
        raise ValidationError("unsupported case-registry schema")
    if data.get("protocol_version") != "E1":
        raise ValidationError("protocol_version must be E1")

    cases = data.get("cases")
    manifests = data.get("pool_manifests")
    if not isinstance(cases, list) or not isinstance(manifests, dict):
        raise ValidationError("cases and pool_manifests are required")
    if set(manifests) != POOLS:
        raise ValidationError("pool_manifests must contain exactly CALIBRATION, BLIND, HOLDOUT")

    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValidationError(f"cases[{index}] must be an object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id.startswith("<"):
            raise ValidationError(f"cases[{index}].case_id must be an opaque non-placeholder ID")
        if case_id in seen:
            raise ValidationError(f"duplicate case_id: {case_id}")
        seen.add(case_id)
        pool = case.get("pool")
        if pool not in POOLS:
            raise ValidationError(f"{case_id}: invalid pool")
        if not case.get("stratum") or str(case.get("stratum")).startswith("<"):
            raise ValidationError(f"{case_id}: pre-outcome stratum required")

        auth = case.get("authorization_status")
        anon = case.get("anonymization_status")
        hashes = case.get("content_hashes")
        if not isinstance(hashes, list):
            raise ValidationError(f"{case_id}: content_hashes must be a list")
        for pos, digest in enumerate(hashes):
            _sha256(digest, f"{case_id}.content_hashes[{pos}]")

        eligible = auth in AUTH_OK and anon in ANON_OK and bool(hashes) and bool(case.get("source_provenance_ref"))
        if case.get("ingestion_allowed") is True and not eligible:
            raise ValidationError(f"{case_id}: ingestion_allowed cannot be true before fail-closed metadata gates pass")
        if sealed and not eligible:
            raise ValidationError(f"{case_id}: sealed registry contains ineligible case")

        history = case.get("access_history")
        if not isinstance(history, list):
            raise ValidationError(f"{case_id}: access_history must be a list")
        for event in history:
            if not isinstance(event, dict) or event.get("content_access") not in CONTENT_ACCESS:
                raise ValidationError(f"{case_id}: malformed access-history event")
            if not event.get("actor_role") or not event.get("purpose") or not event.get("timestamp") or not event.get("protocol_phase"):
                raise ValidationError(f"{case_id}: access-history event missing audit metadata")
            if pool in {"BLIND", "HOLDOUT"} and event.get("content_access") == "content" and event.get("protocol_phase") in {
                "PRE_CALIBRATION", "CALIBRATION", "DEVELOPMENT", "PRE_FREEZE"
            }:
                raise ValidationError(f"{case_id}: BLIND/HOLDOUT contamination detected")

    for pool in POOLS:
        manifest = manifests[pool]
        if not isinstance(manifest, dict):
            raise ValidationError(f"{pool}: pool manifest must be an object")
        if sealed:
            if manifest.get("sealed") is not True or not manifest.get("manifest_id") or not manifest.get("sealed_at"):
                raise ValidationError(f"{pool}: sealed manifest metadata incomplete")
            _sha256(manifest.get("sha256"), f"{pool}.sha256")


def validate_reviewer_protocol(data: dict, *, ready: bool) -> None:
    if data.get("schema") != "thistinti-p1-e1-reviewer-protocol" or data.get("schema_version") != 1:
        raise ValidationError("unsupported reviewer-protocol schema")
    if data.get("protocol_version") != "E1":
        raise ValidationError("reviewer protocol must bind E1")
    reviewers = data.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) != 2:
        raise ValidationError("exactly two independent reviewer records are required")
    ids = []
    for reviewer in reviewers:
        if not isinstance(reviewer, dict):
            raise ValidationError("reviewer record must be an object")
        reviewer_id = reviewer.get("reviewer_id")
        if not isinstance(reviewer_id, str) or not reviewer_id or reviewer_id.startswith("<"):
            if ready:
                raise ValidationError("reviewer_id is missing or placeholder")
            continue
        ids.append(reviewer_id)
        if ready:
            for field in ("competence_attestation_ref", "conflict_declaration_ref", "independence_attestation_ref", "assigned_at"):
                if not reviewer.get(field):
                    raise ValidationError(f"{reviewer_id}: {field} required")
    if ready and len(set(ids)) != 2:
        raise ValidationError("two distinct reviewer identities are required")
    if ready:
        _sha256(data.get("pool_manifest_sha256"), "pool_manifest_sha256")
    reference = data.get("reference_record_contract", {})
    adjudication = data.get("adjudication_contract", {})
    if reference.get("must_be_sealed_before_product_exposure") is not True:
        raise ValidationError("reference records must be sealed before product exposure")
    if adjudication.get("separate_record_required") is not True or adjudication.get("must_preserve_original_reviews") is not True:
        raise ValidationError("adjudication must be separate and preserve original reviews")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--reviewer-protocol", type=Path, required=True)
    parser.add_argument("--sealed", action="store_true", help="Require sealed, eligible pool manifests")
    parser.add_argument("--reviewers-ready", action="store_true", help="Require real reviewer attestations and pool binding")
    args = parser.parse_args()

    registry = _load(args.registry)
    reviewer = _load(args.reviewer_protocol)
    validate_registry(registry, sealed=args.sealed)
    validate_reviewer_protocol(reviewer, ready=args.reviewers_ready)

    # Emit hashes only. Never echo case contents or reviewer reference findings.
    print(json.dumps({
        "result": "VALID_STRUCTURE_NOT_QUALIFICATION_PASS",
        "registry_sha256": hashlib.sha256(args.registry.read_bytes()).hexdigest(),
        "reviewer_protocol_sha256": hashlib.sha256(args.reviewer_protocol.read_bytes()).hexdigest(),
        "sealed_required": args.sealed,
        "reviewers_ready_required": args.reviewers_ready,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
