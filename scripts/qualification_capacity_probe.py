#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
from pathlib import Path
from typing import Any


SCHEMA = "thistinti.qualified-performance-capacity-evidence"


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return round(ordered[index], 3)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def valid_sha(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(ch in "0123456789abcdefABCDEF" for ch in value)


def aggregate_load_reports(paths: list[Path]) -> dict[str, Any]:
    reports = [load_json(path) for path in paths]
    for path, report in zip(paths, reports, strict=True):
        if report.get("schema") != "thistinti.beta-load-probe.v1":
            raise ValueError(f"{path}: unsupported load-probe schema")

    p95s = [float(report["latency_ms"]["p95"]) for report in reports]
    throughputs = [float(report["throughput_requests_per_second"]) for report in reports]
    error_rates = [float(report["error_rate"]) for report in reports]
    durations = [float(report["duration_seconds"]) for report in reports]

    return {
        "repetition_count": len(reports),
        "source_reports": [str(path) for path in paths],
        "latency_p95_ms": {
            "minimum": round(min(p95s), 3) if p95s else None,
            "median": percentile(p95s, 0.50),
            "maximum": round(max(p95s), 3) if p95s else None,
        },
        "throughput_requests_per_second": {
            "minimum": round(min(throughputs), 3) if throughputs else None,
            "median": percentile(throughputs, 0.50),
            "maximum": round(max(throughputs), 3) if throughputs else None,
        },
        "error_rate": {
            "minimum": round(min(error_rates), 6) if error_rates else None,
            "median": percentile(error_rates, 0.50),
            "maximum": round(max(error_rates), 6) if error_rates else None,
        },
        "duration_seconds": {
            "minimum": round(min(durations), 3) if durations else None,
            "median": round(statistics.median(durations), 3) if durations else None,
            "maximum": round(max(durations), 3) if durations else None,
        },
    }


def collect_environment() -> dict[str, Any]:
    return {
        "os": platform.system() or None,
        "os_version": platform.version() or None,
        "cpu": platform.processor() or None,
        "logical_cpu_count": None,
        "ram_bytes": None,
        "disk_type": None,
        "runtime_configuration": None,
        "measurement_tools": ["scripts/qualification_capacity_probe.py"],
    }


def build_record(args: argparse.Namespace) -> dict[str, Any]:
    record = load_json(args.template)
    if record.get("schema") != SCHEMA or record.get("schema_version") != 1:
        raise ValueError("unsupported evidence template schema")

    record["candidate"]["version"] = args.version
    record["candidate"]["source_sha"] = args.source_sha
    record["candidate"]["artifact_name"] = args.artifact_name
    record["candidate"]["artifact_sha256"] = args.artifact_sha256
    record["candidate"]["edition"] = args.edition
    record["workload"]["id"] = args.workload_id
    record["workload"]["classification"] = args.workload_classification
    record["workload"]["definition_ref"] = args.workload_definition_ref
    record["environment"].update(collect_environment())

    if args.load_report:
        record["representative_runs"] = [aggregate_load_reports(args.load_report)]

    return record


def final_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    candidate = record.get("candidate", {})
    workload = record.get("workload", {})
    environment = record.get("environment", {})
    storage = record.get("storage", {})
    stress = record.get("stress", {})
    recovery = record.get("recovery", {})

    if record.get("schema") != SCHEMA or record.get("schema_version") != 1:
        errors.append("schema must be thistinti.qualified-performance-capacity-evidence v1")
    if not valid_sha(candidate.get("source_sha"), 40):
        errors.append("candidate.source_sha must be a full 40-hex SHA")
    if not valid_sha(candidate.get("artifact_sha256"), 64):
        errors.append("candidate.artifact_sha256 must be a full 64-hex SHA-256")
    if not candidate.get("artifact_name"):
        errors.append("candidate.artifact_name is required")
    if candidate.get("edition") not in {"local", "self-hosted"}:
        errors.append("candidate.edition must be local or self-hosted")
    if not workload.get("id") or not workload.get("definition_ref"):
        errors.append("workload identity and definition_ref are required")
    if workload.get("classification") not in {"SYNTHETIC", "PUBLIC_NOT_BLIND", "AUTHORISED_NON_BLIND"}:
        errors.append("workload.classification must explicitly exclude BLIND/HOLDOUT")
    if workload.get("blind_holdout_excluded") is not True:
        errors.append("workload.blind_holdout_excluded must remain true")

    runs = record.get("representative_runs") or []
    repetition_count = sum(int(run.get("repetition_count", 0)) for run in runs if isinstance(run, dict))
    if repetition_count < 3:
        errors.append("at least three representative repetitions are required")

    if not environment.get("os") or not environment.get("cpu"):
        errors.append("environment OS and CPU identity are required")
    if environment.get("ram_bytes") is None:
        errors.append("environment.ram_bytes must be measured")
    if not record.get("idle", {}).get("samples"):
        errors.append("idle resource samples are required")
    if storage.get("before_bytes") is None or storage.get("after_bytes") is None:
        errors.append("storage before/after measurements are required")
    if stress.get("executed") is not True:
        errors.append("a controlled stress point must be executed")
    if recovery.get("backup_duration_seconds") is None or recovery.get("restore_duration_seconds") is None:
        errors.append("backup and restore durations are required")
    if recovery.get("verified_backup_bytes") is None:
        errors.append("verified backup size is required")
    if record.get("release_blocking_defects"):
        errors.append("release_blocking_defects must be empty for final qualification")

    claims = record.get("claims", {})
    if claims.get("universal_scale_claim") is not False:
        errors.append("universal scale claims are forbidden")
    if claims.get("cross_edition_inheritance") is not False:
        errors.append("cross-edition evidence inheritance is forbidden")
    if claims.get("extrapolation_beyond_measured_envelope") is not False:
        errors.append("extrapolation beyond the measured envelope is forbidden")

    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate and structurally validate RELEASE 1.0.0 capacity evidence.")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("docs/templates/qualified-performance-capacity-evidence.v0.1.json"),
    )
    parser.add_argument("--source-sha")
    parser.add_argument("--version")
    parser.add_argument("--artifact-name")
    parser.add_argument("--artifact-sha256")
    parser.add_argument("--edition", choices=["local", "self-hosted"])
    parser.add_argument("--workload-id")
    parser.add_argument("--workload-classification", choices=["SYNTHETIC", "PUBLIC_NOT_BLIND", "AUTHORISED_NON_BLIND"])
    parser.add_argument("--workload-definition-ref")
    parser.add_argument("--load-report", type=Path, action="append", default=[])
    parser.add_argument(
        "--evidence", type=Path, help="Validate an already populated evidence JSON instead of building one"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--final", action="store_true", help="Fail closed unless the evidence is structurally final-ready"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        record = load_json(args.evidence) if args.evidence else build_record(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"capacity evidence error: {exc}", file=sys.stderr)
        return 2

    errors = final_errors(record) if args.final else []
    record["qualification_result"] = "STRUCTURALLY_READY_FOR_REVIEW" if args.final and not errors else "NOT_A_PASS"
    if args.final and not errors:
        record["status"] = "EXECUTED_REQUIRES_HUMAN_REVIEW"

    rendered = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if errors:
        for error in errors:
            print(f"FINAL BLOCKER: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
