#!/usr/bin/env python3
"""Fail-closed structural validator for the E1 Pilot Manifest.

This validator checks only internally knowable integrity properties. It never
asserts that authorisation, reviewer independence, external assessment, human
evidence, signing, recovery, or freeze approval actually happened.
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
POOLS = ("CALIBRATION", "BLIND", "HOLDOUT")
ALLOWED_STATUS = {"PREPARATION_ONLY", "FROZEN"}


class ManifestError(ValueError):
    pass


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{path}: expected object")
    return value


def _require_string(value: Any, path: str, *, allow_placeholder: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{path}: expected non-empty string")
    if not allow_placeholder and PLACEHOLDER.match(value):
        raise ManifestError(f"{path}: unresolved placeholder")
    return value


def _require_sha(
    value: Any,
    path: str,
    pattern: re.Pattern[str],
    *,
    allow_placeholder: bool,
) -> None:
    text = _require_string(value, path, allow_placeholder=allow_placeholder)
    if allow_placeholder and PLACEHOLDER.match(text):
        return
    if not pattern.fullmatch(text):
        raise ManifestError(f"{path}: invalid hash format")


def validate_manifest(data: dict[str, Any], *, final: bool = False) -> None:
    if data.get("manifest_schema_version") != "e1-manifest.v0.1":
        raise ManifestError("manifest_schema_version: unsupported schema")
    if data.get("protocol_version") != "E1":
        raise ManifestError("protocol_version: expected E1")
    if data.get("qualification_claim") != ("ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1"):
        raise ManifestError("qualification_claim: unexpected claim")

    status = data.get("status")
    if status not in ALLOWED_STATUS:
        raise ManifestError("status: expected PREPARATION_ONLY or FROZEN")
    if status == "FROZEN" and not final:
        raise ManifestError("status: FROZEN requires --final validation")
    if final and status != "FROZEN":
        raise ManifestError("status: final validation requires FROZEN")

    scope = _require_mapping(data.get("p1_scope"), "p1_scope")
    _require_string(scope.get("version"), "p1_scope.version", allow_placeholder=not final)
    _require_sha(
        scope.get("sha256"),
        "p1_scope.sha256",
        SHA256,
        allow_placeholder=not final,
    )
    if final and not scope.get("approval_ref"):
        raise ManifestError("p1_scope.approval_ref: required for frozen manifest")

    candidate = _require_mapping(data.get("candidate"), "candidate")
    _require_sha(
        candidate.get("source_sha"),
        "candidate.source_sha",
        SHA40,
        allow_placeholder=not final,
    )
    for field in ("release_version", "engine_version"):
        _require_string(candidate.get(field), f"candidate.{field}", allow_placeholder=not final)
    _require_sha(
        candidate.get("qualification_config_sha256"),
        "candidate.qualification_config_sha256",
        SHA256,
        allow_placeholder=not final,
    )

    parsers = candidate.get("parser_set")
    if not isinstance(parsers, list) or not parsers:
        raise ManifestError("candidate.parser_set: expected non-empty array")
    for index, parser in enumerate(parsers):
        parser_obj = _require_mapping(parser, f"candidate.parser_set[{index}]")
        _require_string(
            parser_obj.get("id"),
            f"candidate.parser_set[{index}].id",
            allow_placeholder=not final,
        )
        _require_string(
            parser_obj.get("version"),
            f"candidate.parser_set[{index}].version",
            allow_placeholder=not final,
        )
        _require_sha(
            parser_obj.get("sha256"),
            f"candidate.parser_set[{index}].sha256",
            SHA256,
            allow_placeholder=not final,
        )

    for component in (
        "rule_pack",
        "practice_model",
        "company_profile",
        "provenance_matrix",
    ):
        item = _require_mapping(candidate.get(component), f"candidate.{component}")
        _require_string(
            item.get("version"),
            f"candidate.{component}.version",
            allow_placeholder=not final,
        )
        _require_sha(
            item.get("sha256"),
            f"candidate.{component}.sha256",
            SHA256,
            allow_placeholder=not final,
        )

    gates = data.get("required_gate_evidence")
    if not isinstance(gates, list):
        raise ManifestError("required_gate_evidence: expected array")
    if final and not gates:
        raise ManifestError("required_gate_evidence: frozen manifest requires gate evidence")
    source_sha = candidate.get("source_sha")
    seen_checks: set[str] = set()
    for index, gate in enumerate(gates):
        gate_obj = _require_mapping(gate, f"required_gate_evidence[{index}]")
        check = _require_string(gate_obj.get("check"), f"required_gate_evidence[{index}].check")
        if check in seen_checks:
            raise ManifestError(f"required_gate_evidence[{index}].check: duplicate check")
        seen_checks.add(check)
        gate_sha = _require_string(
            gate_obj.get("source_sha"),
            f"required_gate_evidence[{index}].source_sha",
        )
        if not PLACEHOLDER.match(str(source_sha)) and gate_sha != source_sha:
            raise ManifestError(f"required_gate_evidence[{index}].source_sha: stale-SHA evidence")
        if gate_obj.get("conclusion") != "success":
            raise ManifestError(f"required_gate_evidence[{index}].conclusion: expected success")

    pools = _require_mapping(data.get("pools"), "pools")
    if set(pools) != set(POOLS):
        raise ManifestError("pools: expected exactly CALIBRATION, BLIND, HOLDOUT")
    for pool_name in POOLS:
        pool = _require_mapping(pools[pool_name], f"pools.{pool_name}")
        _require_string(
            pool.get("manifest_id"),
            f"pools.{pool_name}.manifest_id",
            allow_placeholder=not final,
        )
        _require_sha(
            pool.get("sha256"),
            f"pools.{pool_name}.sha256",
            SHA256,
            allow_placeholder=not final,
        )
        if not isinstance(pool.get("case_count"), int) or pool["case_count"] < 0:
            raise ManifestError(f"pools.{pool_name}.case_count: expected non-negative integer")
        if final and not pool.get("sealed"):
            raise ManifestError(f"pools.{pool_name}.sealed: frozen manifest requires sealed pool")

    reviewer = _require_mapping(data.get("reviewer_protocol"), "reviewer_protocol")
    _require_string(
        reviewer.get("version"),
        "reviewer_protocol.version",
        allow_placeholder=not final,
    )
    _require_sha(
        reviewer.get("sha256"),
        "reviewer_protocol.sha256",
        SHA256,
        allow_placeholder=not final,
    )
    if final and not reviewer.get("reviewers_secured"):
        raise ManifestError("reviewer_protocol.reviewers_secured: required for frozen manifest")
    if final and not reviewer.get("adjudication_protocol_ref"):
        raise ManifestError("reviewer_protocol.adjudication_protocol_ref: required for frozen manifest")

    freeze = _require_mapping(data.get("freeze"), "freeze")
    if final:
        for field in ("approved_by", "approved_at", "freeze_ref"):
            if not freeze.get(field):
                raise ManifestError(f"freeze.{field}: required for frozen manifest")
        if not freeze.get("approved"):
            raise ManifestError("freeze.approved: final validation requires true")

    external = _require_mapping(data.get("external_evidence"), "external_evidence")
    if final:
        if not external.get("authorised_case_sources_secured"):
            raise ManifestError("external_evidence.authorised_case_sources_secured: required")
        if not external.get("independent_reviewers_secured"):
            raise ManifestError("external_evidence.independent_reviewers_secured: required")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true", help="enforce frozen-manifest preconditions")
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManifestError("root: expected object")
    validate_manifest(data, final=args.final)
    print("E1 manifest validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
