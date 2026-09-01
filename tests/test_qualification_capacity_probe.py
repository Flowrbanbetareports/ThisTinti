from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qualification_capacity_probe.py"
spec = importlib.util.spec_from_file_location("qualification_capacity_probe", SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def write_load_report(path: Path, *, p95: float, throughput: float, error_rate: float) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "thistinti.beta-load-probe.v1",
                "duration_seconds": 2.0,
                "throughput_requests_per_second": throughput,
                "error_rate": error_rate,
                "latency_ms": {"p95": p95},
            }
        ),
        encoding="utf-8",
    )


def test_aggregate_requires_real_repetitions(tmp_path: Path) -> None:
    reports = []
    for index, p95 in enumerate((100.0, 120.0, 110.0)):
        path = tmp_path / f"run-{index}.json"
        write_load_report(path, p95=p95, throughput=50.0 + index, error_rate=0.0)
        reports.append(path)

    aggregate = probe.aggregate_load_reports(reports)

    assert aggregate["repetition_count"] == 3
    assert aggregate["latency_p95_ms"]["median"] == 110.0
    assert aggregate["throughput_requests_per_second"]["minimum"] == 50.0


def test_final_validation_fails_closed_on_template() -> None:
    template = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/templates/qualified-performance-capacity-evidence.v0.1.json").read_text(
            encoding="utf-8"
        )
    )

    errors = probe.final_errors(template)

    assert "candidate.source_sha must be a full 40-hex SHA" in errors
    assert "at least three representative repetitions are required" in errors
    assert "a controlled stress point must be executed" in errors
    assert "backup and restore durations are required" in errors


def test_final_validation_accepts_structurally_complete_record() -> None:
    record = {
        "schema": probe.SCHEMA,
        "schema_version": 1,
        "candidate": {
            "source_sha": "a" * 40,
            "artifact_sha256": "b" * 64,
            "artifact_name": "ThisTinti-1.0.0.exe",
            "edition": "local",
        },
        "workload": {
            "id": "synthetic-capacity-v1",
            "definition_ref": "docs/workloads/synthetic-capacity-v1.md",
            "classification": "SYNTHETIC",
            "blind_holdout_excluded": True,
        },
        "environment": {"os": "Windows", "cpu": "example", "ram_bytes": 16_000_000_000},
        "representative_runs": [{"repetition_count": 3}],
        "idle": {"samples": [{"cpu_percent": 1.0, "ram_bytes": 100_000_000}]},
        "storage": {"before_bytes": 100, "after_bytes": 200},
        "stress": {"executed": True},
        "recovery": {
            "backup_duration_seconds": 10.0,
            "restore_duration_seconds": 15.0,
            "verified_backup_bytes": 1_000,
        },
        "release_blocking_defects": [],
        "claims": {
            "universal_scale_claim": False,
            "cross_edition_inheritance": False,
            "extrapolation_beyond_measured_envelope": False,
        },
    }

    assert probe.final_errors(record) == []
