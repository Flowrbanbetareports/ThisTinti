from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from real_pilot_toolkit import (  # noqa: E402
    MEASUREMENT_FIELDS,
    inspect_workspace,
    prepare_workspace,
    summarize_workspace,
)


def test_prepare_workspace_creates_thirty_cases_and_safe_boundaries(tmp_path: Path) -> None:
    manifest = prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)

    assert len(manifest["cases"]) == 30
    assert manifest["authorization"]["status"] == "pending"
    assert manifest["claim_boundary"] == {
        "safe_to_automate": False,
        "commercial_accuracy_claim_allowed": False,
        "production_claim_allowed": False,
    }
    assert (tmp_path / "input" / "CASE-030").is_dir()

    rows = list(csv.DictReader((tmp_path / "measurements.csv").open(encoding="utf-8")))
    assert len(rows) == 30
    assert rows[0]["case_id"] == "CASE-001"


def test_inspection_blocks_detected_identifiers_and_requires_authorization(tmp_path: Path) -> None:
    manifest = prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    manifest["authorization"]["status"] = "approved"
    (tmp_path / "pilot-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (tmp_path / "input" / "CASE-001" / "invoice.json").write_text(
        '{"contact": "persona@example.com"}',
        encoding="utf-8",
    )

    report, valid = inspect_workspace(tmp_path)

    assert valid is False
    assert report["ready_for_execution"] is False
    assert any(item["type"] == "email" for item in report["pii_findings"])


def test_complete_measurements_generate_limited_positive_decision(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    with (tmp_path / "measurements.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_FIELDS)
        writer.writeheader()
        for index in range(1, 31):
            writer.writerow(
                {
                    "case_id": f"CASE-{index:03d}",
                    "reviewer_primary": "REV-A",
                    "reviewer_secondary": "REV-B",
                    "ground_truth_complete": "true",
                    "manual_seconds": "120",
                    "assisted_seconds": "60",
                    "actual_findings": "1",
                    "reported_findings": "1",
                    "false_positives": "0",
                    "false_negatives": "0",
                    "critical_miss": "false",
                    "user_score_1_to_5": "4",
                    "notes": "",
                }
            )

    report, complete = summarize_workspace(tmp_path)

    assert complete is True
    assert report["decision"] == "idoneo_con_revisione_umana"
    assert report["metrics"]["time_saved_percent"] == 50.0
    assert report["claim_boundary"]["production_certification"] is False


def test_false_negative_prevents_unqualified_positive_decision(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    with (tmp_path / "measurements.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_FIELDS)
        writer.writeheader()
        for index in range(1, 31):
            writer.writerow(
                {
                    "case_id": f"CASE-{index:03d}",
                    "reviewer_primary": "REV-A",
                    "reviewer_secondary": "REV-B",
                    "ground_truth_complete": "true",
                    "manual_seconds": "100",
                    "assisted_seconds": "80",
                    "actual_findings": "1",
                    "reported_findings": "0" if index == 1 else "1",
                    "false_positives": "0",
                    "false_negatives": "1" if index == 1 else "0",
                    "critical_miss": "false",
                    "user_score_1_to_5": "3",
                    "notes": "",
                }
            )

    report, complete = summarize_workspace(tmp_path)

    assert complete is True
    assert report["decision"] == "idoneo_solo_con_revisione_rafforzata"
