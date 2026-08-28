from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from procurement_pilot.common import BACKLOG_FIELDS, CASE_REGISTER_FIELDS, RESULT_FIELDS  # noqa: E402
from procurement_pilot.evaluation import evaluate  # noqa: E402
from procurement_pilot.freeze import freeze_workspace  # noqa: E402
from procurement_pilot.ground_truth import (  # noqa: E402
    check_ready,
    create_ground_truth_templates,
    seal_ground_truth,
)
from procurement_pilot.workspace import inventory_private_documents, prepare_workspace  # noqa: E402


def _write_artifacts(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name in [
        "practice-model.json",
        "rule-pack.json",
        "company-profile.json",
        "ground-truth-protocol.json",
        "evaluation-protocol.json",
    ]:
        path = tmp_path / name
        path.write_text('{"version":"test"}\n', encoding="utf-8")
        paths[name] = path
    return paths


def _authorize_and_fill_register(workspace: Path, leak: bool = False) -> None:
    with (workspace / "case-register.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows, start=1):
        row["authorized"] = "true"
        row["source_alias"] = f"SRC-{index:03d}"
        row["template_family"] = f"TPL-{index:03d}"
        row["similarity_group"] = f"SIM-{row['phase']}-{index:03d}"
        row["case_type"] = "standard" if index % 2 else "exception"
    if leak:
        calibration = next(row for row in rows if row["phase"] == "calibration")
        blind = next(row for row in rows if row["phase"] == "blind")
        blind["similarity_group"] = calibration["similarity_group"]
    with (workspace / "case-register.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_REGISTER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _add_documents(workspace: Path) -> None:
    with (workspace / "case-register.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        path = workspace / row["phase"] / row["case_id"] / "document.txt"
        path.write_text(f"authorized test document {row['case_id']}\n", encoding="utf-8")


def _freeze(workspace: Path, artifacts: dict[str, Path]) -> None:
    freeze_workspace(
        workspace,
        software_commit="a" * 40,
        software_version="3.4.0-alpha.7-rc.15",
        practice_model=artifacts["practice-model.json"],
        practice_model_version="0.1",
        rule_pack=artifacts["rule-pack.json"],
        rule_pack_version="0.1",
        company_profile=artifacts["company-profile.json"],
        company_profile_version="0.1",
        ground_truth_protocol=artifacts["ground-truth-protocol.json"],
        ground_truth_protocol_version="1",
        evaluation_protocol=artifacts["evaluation-protocol.json"],
        evaluation_protocol_version="1",
    )


def _complete_ground_truth(workspace: Path) -> None:
    manifest = json.loads((workspace / "pilot-manifest.json").read_text(encoding="utf-8"))
    for case_id in manifest["case_register"]["blind_case_ids"]:
        for folder, reviewer in [("reviewer-a", "REV-A"), ("reviewer-b", "REV-B")]:
            path = workspace / "ground-truth" / folder / f"{case_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["status"] = "complete"
            payload["reviewer_id"] = reviewer
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        path = workspace / "ground-truth" / "adjudicated" / f"{case_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["review"].update(
            {
                "reviewer_a_completed": True,
                "reviewer_b_completed": True,
                "adjudication_status": "sealed",
                "disagreement_count": 0,
            }
        )
        payload["expected"] = [
            {
                "expectation_id": "EXP-1",
                "presence": "present",
                "evidentiary_sufficiency": "sufficient",
            }
        ]
        payload["observed"] = {
            "evidence": [{"evidence_id": "EV-1", "source_ref": "document.txt"}],
            "facts": [
                {
                    "fact_id": "FACT-1",
                    "value": "example",
                    "evidence_refs": ["EV-1"],
                }
            ],
            "interpretations": [
                {
                    "interpretation_id": "INT-1",
                    "fact_refs": ["FACT-1"],
                    "rule_ref": "identity-linkage",
                }
            ],
        }
        payload["judged"] = {
            "findings": [
                {
                    "finding_id": "F-1",
                    "impact_type": "informational",
                    "financial_status": "not_applicable",
                }
            ]
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_prepare_encodes_calibration_blind_and_preregistration(tmp_path: Path) -> None:
    plan = prepare_workspace(tmp_path, "PROC-001", "ORG-001", 5, 20)
    assert plan["methodology"]["calibration_case_count"] == 5
    assert plan["methodology"]["blind_case_count"] == 20
    assert plan["preregistration"]["acceptance_thresholds"]["critical_misses_max"] == 0
    assert plan["claim_boundary"]["general_procurement_accuracy_claim_allowed"] is False


def test_freeze_blocks_similarity_leakage(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    prepare_workspace(workspace, "PROC-002", "ORG-001", 5, 20)
    _authorize_and_fill_register(workspace, leak=True)
    _add_documents(workspace)
    inventory_private_documents(workspace)
    artifacts = _write_artifacts(tmp_path)
    try:
        _freeze(workspace, artifacts)
    except ValueError as exc:
        assert "leakage" in str(exc)
    else:
        raise AssertionError("freeze should reject similarity leakage")


def test_full_blind_protocol_seals_and_reports_without_general_claim(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    prepare_workspace(workspace, "PROC-003", "ORG-001", 5, 20)
    _authorize_and_fill_register(workspace)
    _add_documents(workspace)
    inventory = inventory_private_documents(workspace)
    assert inventory["cases_without_documents"] == []

    artifacts = _write_artifacts(tmp_path)
    _freeze(workspace, artifacts)
    created = create_ground_truth_templates(workspace)
    assert len(created["created_case_ids"]) == 20
    _complete_ground_truth(workspace)
    seal = seal_ground_truth(workspace)
    assert seal["blind_case_count"] == 20
    assert check_ready(workspace)["ready_for_blind_run"] is True

    manifest = json.loads((workspace / "pilot-manifest.json").read_text(encoding="utf-8"))
    with (workspace / "results" / "blind-results.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for case_id in manifest["case_register"]["blind_case_ids"]:
            writer.writerow(
                {
                    "case_id": case_id,
                    "true_positives": "1",
                    "false_positives": "0",
                    "false_negatives": "0",
                    "critical_miss": "false",
                    "potential_exposure_detected": "100",
                    "potential_exposure_missed": "0",
                    "confirmed_loss": "0",
                    "avoided_loss": "0",
                    "currency": "EUR",
                    "notes": "",
                }
            )

    report = evaluate(workspace)
    assert report["overall"]["raw_counts"]["true_positives"] == 20
    assert set(report["results_by_case_type"]) == {"exception", "standard"}
    assert report["economics"]["exposure_weighted_recall"] == 1.0
    assert report["claim_boundary"]["general_procurement_accuracy_claim_allowed"] is False
    assert report["decision"] == "blind_run_completed_no_critical_miss_observed"
    with (workspace / "results" / "blind-backlog.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == BACKLOG_FIELDS
        assert list(reader) == []


def test_frozen_artifact_change_invalidates_ready_state(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    prepare_workspace(workspace, "PROC-004", "ORG-001", 5, 20)
    _authorize_and_fill_register(workspace)
    _add_documents(workspace)
    inventory_private_documents(workspace)
    artifacts = _write_artifacts(tmp_path)
    _freeze(workspace, artifacts)
    create_ground_truth_templates(workspace)
    _complete_ground_truth(workspace)
    seal_ground_truth(workspace)
    assert check_ready(workspace)["ready_for_blind_run"] is True

    artifacts["rule-pack.json"].write_text('{"changed":true}\n', encoding="utf-8")
    readiness = check_ready(workspace)
    assert readiness["ready_for_blind_run"] is False
    assert any("rule_pack" in error for error in readiness["errors"])
