import json
from pathlib import Path

import pytest

from scripts.validate_pilot_dataset import validate_path


def _payload(scenarios: int = 30) -> dict:
    return {
        "name": "Governed pilot",
        "version": "1",
        "evidence_level": "anonymized_pilot",
        "evidence": {
            "authorization_reference": "AUTH-001",
            "authorized_use_confirmed": True,
            "anonymization_confirmed": True,
            "anonymization_method": "Direct identifiers and business references were replaced before ingestion.",
            "reviewer_refs": ["reviewer-a", "reviewer-b"],
            "ground_truth_method": "Two independent reviewers classify every scenario and reconcile disagreements.",
            "scope": "Thirty anonymized order scenarios from a controlled pilot perimeter.",
            "prepared_at": "2025-01-01T00:00:00Z",
        },
        "scenarios": [
            {
                "id": f"scenario-{index}",
                "documents": [
                    {
                        "filename": f"order-{index}.json",
                        "content": {
                            "document_type": "order",
                            "number": f"ORDER-{index}",
                            "supplier_name": "Supplier Pseudonym",
                            "lines": [{"sku": f"SKU-{index}", "quantity": 1, "unit_price": 1}],
                        },
                    }
                ],
                "expected": [],
            }
            for index in range(scenarios)
        ],
    }


def test_pilot_dataset_inspection_reports_composition(tmp_path: Path):
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")
    report = validate_path(path)
    assert report["ready_for_controlled_pilot"] is True
    assert report["scenario_count"] == 30
    assert report["document_count"] == 30
    assert report["document_types"] == {"order": 30}
    assert report["governance"]["reviewer_count"] == 2
    assert len(report["sha256"]) == 64


def test_pilot_dataset_inspection_flags_possible_sensitive_values(tmp_path: Path):
    payload = _payload()
    payload["scenarios"][0]["documents"][0]["content"]["contact_email"] = "person@example.com"
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = validate_path(path)
    codes = {warning["code"] for warning in report["warnings"]}
    assert "sensitive-key" in codes
    assert "email" in codes


def test_pilot_dataset_inspection_rejects_undersized_real_dataset(tmp_path: Path):
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(_payload(scenarios=29)), encoding="utf-8")
    with pytest.raises(ValueError, match="30"):
        validate_path(path)
