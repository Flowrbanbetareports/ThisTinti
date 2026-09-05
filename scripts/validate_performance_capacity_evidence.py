#!/usr/bin/env python3
"""Validate #166 performance/capacity evidence structure.

This validator checks evidence completeness and release-gate structure only. It
cannot execute measurements, authenticate operators, or declare qualification.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_SIZES = ("small", "representative", "stress")


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith("<")


def _refs(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_nonempty(item) for item in value)


def _positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def validate(data: dict, final: bool = False) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "thistinti-performance-capacity-evidence":
        errors.append("schema must be thistinti-performance-capacity-evidence")
    if data.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if data.get("qualification_result") != "NOT_A_PASS":
        errors.append("validator input cannot itself declare qualification PASS")

    candidate = data.get("candidate") or {}
    if candidate.get("release_version") != "1.0.0":
        errors.append("candidate.release_version must be 1.0.0")
    if candidate.get("release_tag") != "v1.0.0":
        errors.append("candidate.release_tag must be v1.0.0")

    workload = data.get("workload") or {}
    if workload.get("classification") != "NON_BLIND_ONLY":
        errors.append("workload.classification must remain NON_BLIND_ONLY")
    if workload.get("blind_or_holdout_used") is not False:
        errors.append("BLIND/HOLDOUT material is forbidden in the performance campaign")

    if not final:
        if data.get("status") != "PREPARATION_ONLY_NOT_EXECUTED":
            errors.append("preparation status must remain PREPARATION_ONLY_NOT_EXECUTED")
        return errors

    if data.get("status") != "EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION":
        errors.append("final status must be EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION")
    if not SHA40.fullmatch(str(candidate.get("source_sha") or "")):
        errors.append("candidate.source_sha must be a full 40-hex SHA")
    if not _nonempty(candidate.get("artifact_identity")):
        errors.append("candidate.artifact_identity is required")
    if not SHA256.fullmatch(str(candidate.get("artifact_sha256") or "")):
        errors.append("candidate.artifact_sha256 must be 64 lowercase hex")
    for key in ("edition", "os", "runtime"):
        if not _nonempty(candidate.get(key)):
            errors.append(f"candidate.{key} is required")

    hardware = candidate.get("hardware") or {}
    for key in ("cpu", "storage_type"):
        if not _nonempty(hardware.get(key)):
            errors.append(f"candidate.hardware.{key} is required")
    for key in ("cores", "ram_bytes", "free_storage_bytes_before_run"):
        if not _positive(hardware.get(key)):
            errors.append(f"candidate.hardware.{key} must be measured and > 0")

    database = candidate.get("database") or {}
    for key in ("engine", "version", "configuration_ref"):
        if not _nonempty(database.get(key)):
            errors.append(f"candidate.database.{key} is required")

    if not _nonempty(workload.get("manifest_ref")):
        errors.append("workload.manifest_ref is required")
    if not SHA256.fullmatch(str(workload.get("manifest_sha256") or "")):
        errors.append("workload.manifest_sha256 must be 64 lowercase hex")
    if workload.get("frozen_before_execution") is not True:
        errors.append("workload must be frozen before execution")
    sizes = workload.get("sizes") or {}
    for size in REQUIRED_SIZES:
        entry = sizes.get(size) or {}
        for key in ("documents", "practices"):
            if not _positive(entry.get(key)):
                errors.append(f"workload.sizes.{size}.{key} must be fixed and > 0")

    measurements = data.get("measurements") or {}
    for key in ("installer_bytes", "post_install_bytes"):
        if not _positive(measurements.get(key)):
            errors.append(f"measurements.{key} must be measured and > 0")

    idle = measurements.get("idle") or {}
    for key in ("window_seconds", "ram_bytes"):
        if not _positive(idle.get(key)):
            errors.append(f"measurements.idle.{key} must be measured and > 0")
    cpu = idle.get("cpu_percent")
    if not isinstance(cpu, (int, float)) or isinstance(cpu, bool) or cpu < 0:
        errors.append("measurements.idle.cpu_percent must be measured and >= 0")
    if not _refs(idle.get("evidence_refs")):
        errors.append("measurements.idle.evidence_refs requires real references")

    runs = measurements.get("runs")
    if not isinstance(runs, list):
        errors.append("measurements.runs must be a list")
        runs = []
    by_size: dict[str, list[dict]] = {size: [] for size in REQUIRED_SIZES}
    for run in runs:
        if not isinstance(run, dict):
            errors.append("each measurement run must be an object")
            continue
        size = run.get("workload_size")
        if size not in by_size:
            errors.append("each run workload_size must be small, representative, or stress")
            continue
        by_size[size].append(run)
        if not _nonempty(run.get("started_at_utc")) or not _nonempty(run.get("ended_at_utc")):
            errors.append(f"{size} run requires UTC start/end timestamps")
        for key in ("elapsed_seconds", "throughput_practices_per_second", "peak_ram_bytes", "peak_cpu_percent"):
            if not _positive(run.get(key)):
                errors.append(f"{size} run {key} must be measured and > 0")
        latencies = run.get("latency_seconds") or {}
        for key in ("median", "p95"):
            if not _positive(latencies.get(key)):
                errors.append(f"{size} run latency_seconds.{key} must be measured and > 0")
        if not _refs(run.get("evidence_refs")):
            errors.append(f"{size} run evidence_refs requires real references")
    for size, items in by_size.items():
        if len(items) < 3:
            errors.append(f"{size} requires at least 3 recorded repetitions")

    storage = measurements.get("storage_growth") or {}
    for key in ("database_bytes", "canonical_evidence_snapshot_bytes", "logs_bytes"):
        value = storage.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"measurements.storage_growth.{key} must be measured and >= 0")
    temp = storage.get("quarantine_or_temp_bytes")
    if not isinstance(temp, int) or isinstance(temp, bool) or temp < 0:
        errors.append("measurements.storage_growth.quarantine_or_temp_bytes must be measured and >= 0")
    if not _refs(storage.get("evidence_refs")):
        errors.append("measurements.storage_growth.evidence_refs requires real references")

    backup = measurements.get("backup") or {}
    for key in ("duration_seconds", "artifact_bytes"):
        if not _positive(backup.get(key)):
            errors.append(f"measurements.backup.{key} must be measured and > 0")
    if not SHA256.fullmatch(str(backup.get("sha256") or "")):
        errors.append("measurements.backup.sha256 must be 64 lowercase hex")
    if backup.get("verified") is not True:
        errors.append("measurements.backup.verified must be true")
    if not _refs(backup.get("evidence_refs")):
        errors.append("measurements.backup.evidence_refs requires real references")

    restore = measurements.get("restore") or {}
    if not _positive(restore.get("duration_seconds")):
        errors.append("measurements.restore.duration_seconds must be measured and > 0")
    if restore.get("verification_result") != "PASS":
        errors.append("measurements.restore.verification_result must be PASS")
    if restore.get("cross_reference") != "#168":
        errors.append("measurements.restore.cross_reference must remain #168")
    if not _refs(restore.get("evidence_refs")):
        errors.append("measurements.restore.evidence_refs requires real references")

    limits = data.get("limits") or {}
    if not isinstance(limits.get("hard_product_limits"), list) or not limits.get("hard_product_limits"):
        errors.append("limits.hard_product_limits must record the enforced product limits")
    if not isinstance(limits.get("tested_limits"), list) or not limits.get("tested_limits"):
        errors.append("limits.tested_limits must record the bounded tested envelope")
    if not isinstance(limits.get("observed_degradation"), list):
        errors.append("limits.observed_degradation must be a list")
    if limits.get("stress_outcome") not in {"PASS", "DEGRADED_FAIL_CLOSED"}:
        errors.append("limits.stress_outcome must be PASS or DEGRADED_FAIL_CLOSED")

    claims = data.get("claims") or {}
    if not _nonempty(claims.get("customer_facing_envelope_ref")):
        errors.append("claims.customer_facing_envelope_ref is required")
    if claims.get("cross_edition_equivalence_claimed") is not False:
        errors.append("cross-edition equivalence cannot be claimed without separate evidence")
    if claims.get("unmeasured_scale_claimed") is not False:
        errors.append("unmeasured scale claims are forbidden")

    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
    else:
        for finding in findings:
            if finding.get("release_blocking") is True and finding.get("status") != "CLOSED_RETESTED":
                errors.append("release-blocking performance findings must be CLOSED_RETESTED")

    if not _refs(data.get("evidence_index")):
        errors.append("evidence_index requires real references")
    result = data.get("result") or {}
    if result.get("classification") != "MEASURED":
        errors.append("result.classification must be MEASURED for final structural completeness")
    if result.get("blockers") != []:
        errors.append("result.blockers must be empty for the intended release envelope")
    if not isinstance(result.get("residual_limitations"), list):
        errors.append("result.residual_limitations must be a list")
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
    errors = validate(data, final=args.final)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print("VALID_STRUCTURE_NOT_QUALIFICATION_PASS" if args.final else "VALID_PREPARATION_NOT_A_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
