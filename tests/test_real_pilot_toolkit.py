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
    project_version,
    summarize_workspace,
)


def _authorize_workspace(workspace: Path) -> dict:
    manifest_path = workspace / "pilot-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["authorization"].update(
        {
            "status": "approved",
            "authorized_by_role": "pilot-owner",
            "authorized_at": "2026-08-28T12:00:00Z",
        }
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (workspace / "AUTHORIZATION.md").write_text(
        "# Autorizzazione pilot\n\nStato: APPROVATO E FIRMATO.\n",
        encoding="utf-8",
    )
    return manifest


def _write_complete_measurements(workspace: Path, false_negative_at: int | None = None) -> None:
    with (workspace / "measurements.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_FIELDS)
        writer.writeheader()
        for index in range(1, 31):
            false_negative = index == false_negative_at
            writer.writerow(
                {
                    "case_id": f"CASE-{index:03d}",
                    "reviewer_primary": "REV-A",
                    "reviewer_secondary": "REV-B",
                    "ground_truth_complete": "true",
                    "manual_seconds": "120" if false_negative_at is None else "100",
                    "assisted_seconds": "60" if false_negative_at is None else "80",
                    "actual_findings": "1",
                    "reported_findings": "0" if false_negative else "1",
                    "false_positives": "0",
                    "false_negatives": "1" if false_negative else "0",
                    "critical_miss": "false",
                    "user_score_1_to_5": "4" if false_negative_at is None else "3",
                    "notes": "",
                }
            )


def test_prepare_workspace_creates_thirty_cases_and_safe_boundaries(tmp_path: Path) -> None:
    manifest = prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)

    assert len(manifest["cases"]) == 30
    assert manifest["application"] == {"name": "thistinti", "version": project_version()}
    assert manifest["authorization"]["status"] == "pending"
    assert manifest["manual_review"]["binary_documents_confirmed"] is False
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
    _ = prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    _authorize_workspace(tmp_path)
    (tmp_path / "input" / "CASE-001" / "invoice.json").write_text(
        '{"contact": "persona@example.com"}',
        encoding="utf-8",
    )

    report, valid = inspect_workspace(tmp_path)

    assert valid is False
    assert report["ready_for_execution"] is False
    assert any(item["type"] == "email" for item in report["pii_findings"])


def test_summary_fails_closed_without_authorization_even_with_complete_measurements(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    _write_complete_measurements(tmp_path)

    report, complete = summarize_workspace(tmp_path)

    assert complete is False
    assert report["decision"] == "incompleto"
    assert report["inspection"]["ready_for_execution"] is False
    assert any("autorizzazione non ancora approvata" in item for item in report["errors"])
    assert any("AUTHORIZATION.md non compilato e firmato" in item for item in report["errors"])


def test_binary_documents_require_explicit_manual_review_confirmation(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    manifest = _authorize_workspace(tmp_path)
    (tmp_path / "input" / "CASE-001" / "scan.pdf").write_bytes(b"%PDF-1.4\n% synthetic binary marker\n")

    blocked, valid = inspect_workspace(tmp_path)

    assert valid is True
    assert blocked["ready_for_execution"] is False
    assert "revisione manuale dei documenti binari non attestata" in blocked["blocking_conditions"]

    manifest["manual_review"].update(
        {
            "binary_documents_confirmed": True,
            "confirmed_by_role": "privacy-reviewer",
            "confirmed_at": "2026-08-28T12:05:00Z",
        }
    )
    (tmp_path / "pilot-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ready, valid = inspect_workspace(tmp_path)

    assert valid is True
    assert ready["ready_for_execution"] is True
    assert ready["binary_manual_review"] == ["input/CASE-001/scan.pdf"]


def test_inspection_rejects_workspace_from_other_application_version(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    manifest = _authorize_workspace(tmp_path)
    manifest["application"]["version"] = "0.0.0"
    (tmp_path / "pilot-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report, valid = inspect_workspace(tmp_path)

    assert valid is False
    assert report["ready_for_execution"] is False
    assert "versione ThisTinti del manifest diversa dalla versione in esecuzione" in report["errors"]


def test_complete_measurements_generate_limited_positive_decision(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    _authorize_workspace(tmp_path)
    _write_complete_measurements(tmp_path)

    report, complete = summarize_workspace(tmp_path)

    assert complete is True
    assert report["decision"] == "idoneo_con_revisione_umana"
    assert report["metrics"]["time_saved_percent"] == 50.0
    assert report["inspection"]["ready_for_execution"] is True
    assert len(report["inspection"]["sha256"]) == 64
    assert report["claim_boundary"]["production_certification"] is False


def test_summary_rejects_measurement_case_ids_not_matching_manifest(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    _authorize_workspace(tmp_path)
    _write_complete_measurements(tmp_path)
    rows = list(csv.DictReader((tmp_path / "measurements.csv").open(encoding="utf-8")))
    rows[-1]["case_id"] = "CASE-001"
    with (tmp_path / "measurements.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    report, complete = summarize_workspace(tmp_path)

    assert complete is False
    assert report["decision"] == "incompleto"
    assert "measurements.csv deve contenere esattamente una riga per ogni case_id del manifest" in report["errors"]


def test_false_negative_prevents_unqualified_positive_decision(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "APPAREL-001", "ORG-001", 30)
    _authorize_workspace(tmp_path)
    _write_complete_measurements(tmp_path, false_negative_at=1)

    report, complete = summarize_workspace(tmp_path)

    assert complete is True
    assert report["decision"] == "idoneo_solo_con_revisione_rafforzata"
