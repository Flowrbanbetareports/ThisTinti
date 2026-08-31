#!/usr/bin/env python3
"""Fail-closed structural validator for the E1 Pilot Manifest.

The validator checks internally knowable consistency only. It never proves
that authorisation, anonymisation, reviewer independence, segregation,
external assessment, signing, recovery, or freeze approval actually happened.
References in the manifest must be backed by evidence held by the authorised
custodian/reviewer workflow.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"^<.*>$")
POOLS = ("CALIBRATION", "BLIND", "HOLDOUT")
ALLOWED_STATUS = {"PREPARATION_ONLY", "FROZEN"}
REQUIRED_QUALIFICATION_CHECKS = frozenset(
    {
        "quality",
        "qualify-deep-profile",
        "internal-gates",
        "docker-reference-proof",
        "source-verification",
        "windows-installer",
        "postgres-external-proof",
        "python-compatibility (3.11)",
        "python-compatibility (3.12)",
        "dependency-audit",
    }
)


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


def _require_timestamp(value: Any, path: str) -> datetime:
    text = _require_string(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError(f"{path}: invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ManifestError(f"{path}: timezone required")
    return parsed


def _require_real_ref(value: Any, path: str) -> str:
    return _require_string(value, path, allow_placeholder=False)


def _validate_pool_shape(pool_name: str, pool: dict[str, Any], *, strict: bool) -> None:
    _require_string(
        pool.get("manifest_id"),
        f"pools.{pool_name}.manifest_id",
        allow_placeholder=not strict,
    )
    _require_sha(
        pool.get("sha256"),
        f"pools.{pool_name}.sha256",
        SHA256,
        allow_placeholder=not strict,
    )
    case_count = pool.get("case_count")
    if not isinstance(case_count, int) or isinstance(case_count, bool) or case_count < 0:
        raise ManifestError(f"pools.{pool_name}.case_count: expected non-negative integer")
    if not isinstance(pool.get("sealed"), bool):
        raise ManifestError(f"pools.{pool_name}.sealed: expected boolean")
    policy = _require_mapping(pool.get("access_policy"), f"pools.{pool_name}.access_policy")
    if not isinstance(policy.get("developer_access_before_release"), bool):
        raise ManifestError(
            f"pools.{pool_name}.access_policy.developer_access_before_release: expected boolean"
        )
    _require_string(
        policy.get("release_condition"),
        f"pools.{pool_name}.access_policy.release_condition",
        allow_placeholder=not strict,
    )


def _validate_segregation(data: dict[str, Any], *, before_calibration: bool) -> None:
    """Validate declared pool segregation without inspecting any case contents."""

    scope = _require_mapping(data.get("p1_scope"), "p1_scope")
    _require_string(scope.get("version"), "p1_scope.version")
    _require_sha(scope.get("sha256"), "p1_scope.sha256", SHA256, allow_placeholder=False)
    _require_real_ref(scope.get("approval_ref"), "p1_scope.approval_ref")

    pools = _require_mapping(data.get("pools"), "pools")
    manifest_ids: set[str] = set()
    pool_hashes: set[str] = set()
    sealed_times: list[datetime] = []
    for pool_name in POOLS:
        pool = _require_mapping(pools[pool_name], f"pools.{pool_name}")
        _validate_pool_shape(pool_name, pool, strict=True)
        manifest_id = str(pool["manifest_id"])
        if manifest_id in manifest_ids:
            raise ManifestError(f"pools.{pool_name}.manifest_id: duplicate across pools")
        manifest_ids.add(manifest_id)
        pool_hash = str(pool["sha256"])
        if pool_hash in pool_hashes:
            raise ManifestError(f"pools.{pool_name}.sha256: duplicate across pools")
        pool_hashes.add(pool_hash)
        if pool["case_count"] <= 0:
            raise ManifestError(f"pools.{pool_name}.case_count: must be > 0")
        if pool.get("sealed") is not True:
            raise ManifestError(f"pools.{pool_name}.sealed: must be true")
        sealed_times.append(_require_timestamp(pool.get("sealed_at"), f"pools.{pool_name}.sealed_at"))
        for field in (
            "authorization_evidence_ref",
            "anonymization_evidence_ref",
            "custodian_ref",
        ):
            _require_real_ref(pool.get(field), f"pools.{pool_name}.{field}")
        if pool_name in {"BLIND", "HOLDOUT"}:
            policy = _require_mapping(pool.get("access_policy"), f"pools.{pool_name}.access_policy")
            if policy.get("developer_access_before_release") is not False:
                raise ManifestError(
                    f"pools.{pool_name}.access_policy.developer_access_before_release: must be false"
                )
            if before_calibration and pool.get("opened_at") is not None:
                raise ManifestError(f"pools.{pool_name}.opened_at: must be null before calibration")

    calibration_count = pools["CALIBRATION"]["case_count"]
    blind_count = pools["BLIND"]["case_count"]
    if not 5 <= calibration_count <= 10:
        raise ManifestError("pools.CALIBRATION.case_count: E1 requires 5-10 cases")
    if not 20 <= blind_count <= 25:
        raise ManifestError("pools.BLIND.case_count: E1 requires 20-25 cases")

    segregation = _require_mapping(data.get("segregation"), "segregation")
    if segregation.get("pool_assignment_frozen_before_calibration") is not True:
        raise ManifestError(
            "segregation.pool_assignment_frozen_before_calibration: must be true"
        )
    similarity = _require_mapping(
        segregation.get("cross_pool_similarity_check"),
        "segregation.cross_pool_similarity_check",
    )
    if similarity.get("status") != "PASSED":
        raise ManifestError("segregation.cross_pool_similarity_check.status: expected PASSED")
    _require_real_ref(
        similarity.get("evidence_ref"),
        "segregation.cross_pool_similarity_check.evidence_ref",
    )
    for field in ("access_control_evidence_ref", "assignment_evidence_ref"):
        _require_real_ref(segregation.get(field), f"segregation.{field}")

    timeline = _require_mapping(data.get("timeline"), "timeline")
    pools_sealed_at = _require_timestamp(timeline.get("pools_sealed_at"), "timeline.pools_sealed_at")
    if any(sealed_at > pools_sealed_at for sealed_at in sealed_times):
        raise ManifestError("timeline.pools_sealed_at: cannot precede a pool seal timestamp")
    if before_calibration:
        for field in ("calibration_started_at", "blind_started_at", "holdout_started_at"):
            if timeline.get(field) is not None:
                raise ManifestError(f"timeline.{field}: must be null at pre-calibration gate")

    reviewer = _require_mapping(data.get("reviewer_protocol"), "reviewer_protocol")
    _require_string(reviewer.get("version"), "reviewer_protocol.version")
    _require_sha(reviewer.get("sha256"), "reviewer_protocol.sha256", SHA256, allow_placeholder=False)
    if reviewer.get("reviewers_secured") is not True:
        raise ManifestError("reviewer_protocol.reviewers_secured: required")
    reviewer_refs = reviewer.get("reviewer_refs")
    if not isinstance(reviewer_refs, list) or len(reviewer_refs) < 2:
        raise ManifestError("reviewer_protocol.reviewer_refs: at least two reviewers required")
    normalized_refs = [_require_real_ref(ref, "reviewer_protocol.reviewer_refs[]") for ref in reviewer_refs]
    if len(set(normalized_refs)) != len(normalized_refs):
        raise ManifestError("reviewer_protocol.reviewer_refs: duplicate reviewer reference")
    if reviewer.get("independent_review_required") is not True:
        raise ManifestError("reviewer_protocol.independent_review_required: must remain true")
    if reviewer.get("reviewers_must_not_see_thistinti_output_before_submission") is not True:
        raise ManifestError(
            "reviewer_protocol.reviewers_must_not_see_thistinti_output_before_submission: must remain true"
        )
    _require_real_ref(
        reviewer.get("adjudication_protocol_ref"),
        "reviewer_protocol.adjudication_protocol_ref",
    )

    external = _require_mapping(data.get("external_evidence"), "external_evidence")
    if external.get("authorised_case_sources_secured") is not True:
        raise ManifestError("external_evidence.authorised_case_sources_secured: required")
    if external.get("independent_reviewers_secured") is not True:
        raise ManifestError("external_evidence.independent_reviewers_secured: required")


def validate_manifest(
    data: dict[str, Any],
    *,
    pre_calibration: bool = False,
    final: bool = False,
) -> None:
    if pre_calibration and final:
        raise ManifestError("validation mode: choose --pre-calibration or --final")
    if data.get("manifest_schema_version") != "e1-manifest.v0.2":
        raise ManifestError("manifest_schema_version: unsupported schema")
    if data.get("protocol_version") != "E1":
        raise ManifestError("protocol_version: expected E1")
    if data.get("qualification_claim") != (
        "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1"
    ):
        raise ManifestError("qualification_claim: unexpected claim")

    status = data.get("status")
    if status not in ALLOWED_STATUS:
        raise ManifestError("status: expected PREPARATION_ONLY or FROZEN")
    if status == "FROZEN" and not final:
        raise ManifestError("status: FROZEN requires --final validation")
    if final and status != "FROZEN":
        raise ManifestError("status: final validation requires FROZEN")

    scope = _require_mapping(data.get("p1_scope"), "p1_scope")
    _require_string(
        scope.get("version"),
        "p1_scope.version",
        allow_placeholder=not (pre_calibration or final),
    )
    _require_sha(
        scope.get("sha256"),
        "p1_scope.sha256",
        SHA256,
        allow_placeholder=not (pre_calibration or final),
    )
    if (pre_calibration or final) and not scope.get("approval_ref"):
        raise ManifestError("p1_scope.approval_ref: required")

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
    for index, parser_item in enumerate(parsers):
        parser_obj = _require_mapping(parser_item, f"candidate.parser_set[{index}]")
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

    for component in ("rule_pack", "practice_model", "company_profile", "provenance_matrix"):
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
    if final:
        missing_checks = sorted(REQUIRED_QUALIFICATION_CHECKS - seen_checks)
        if missing_checks:
            raise ManifestError(
                "required_gate_evidence: missing required checks: " + ", ".join(missing_checks)
            )

    pools = _require_mapping(data.get("pools"), "pools")
    if set(pools) != set(POOLS):
        raise ManifestError("pools: expected exactly CALIBRATION, BLIND, HOLDOUT")
    for pool_name in POOLS:
        pool = _require_mapping(pools[pool_name], f"pools.{pool_name}")
        _validate_pool_shape(pool_name, pool, strict=pre_calibration or final)

    reviewer = _require_mapping(data.get("reviewer_protocol"), "reviewer_protocol")
    _require_string(
        reviewer.get("version"),
        "reviewer_protocol.version",
        allow_placeholder=not (pre_calibration or final),
    )
    _require_sha(
        reviewer.get("sha256"),
        "reviewer_protocol.sha256",
        SHA256,
        allow_placeholder=not (pre_calibration or final),
    )

    claim_boundary = _require_mapping(data.get("claim_boundary"), "claim_boundary")
    for field in (
        "manifest_completeness_is_not_qualification",
        "self_declared_fields_are_not_external_evidence",
        "not_blind_material_cannot_substitute_blind_or_holdout",
    ):
        if claim_boundary.get(field) is not True:
            raise ManifestError(f"claim_boundary.{field}: must remain true")

    if pre_calibration:
        _validate_segregation(data, before_calibration=True)

    freeze = _require_mapping(data.get("freeze"), "freeze")
    external = _require_mapping(data.get("external_evidence"), "external_evidence")
    if final:
        _validate_segregation(data, before_calibration=False)
        for field in ("approved_by", "approved_at", "freeze_ref"):
            _require_real_ref(freeze.get(field), f"freeze.{field}")
        if freeze.get("approved") is not True:
            raise ManifestError("freeze.approved: final validation requires true")
        if external.get("authorised_case_sources_secured") is not True:
            raise ManifestError("external_evidence.authorised_case_sources_secured: required")
        if external.get("independent_reviewers_secured") is not True:
            raise ManifestError("external_evidence.independent_reviewers_secured: required")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate E1 manifest structure. PASS means structural consistency only, "
            "never qualification or external-evidence validity."
        )
    )
    parser.add_argument("manifest", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--pre-calibration",
        action="store_true",
        help="fail closed unless three pools are declared sealed/segregated before calibration",
    )
    modes.add_argument("--final", action="store_true", help="enforce frozen-manifest preconditions")
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManifestError("root: expected object")
    validate_manifest(data, pre_calibration=args.pre_calibration, final=args.final)
    mode = "PRE-CALIBRATION" if args.pre_calibration else "FINAL" if args.final else "PREPARATION"
    print(
        f"E1 manifest structural validation: PASS ({mode}); "
        "qualification/external evidence: NOT ASSERTED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
