from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from app.schemas import ValidationDatasetPayload

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "samples" / "public_evidence_benchmark_30_sources.json"
BUILDER = ROOT / "scripts" / "build_public_evidence_benchmark.py"


def _build(tmp_path: Path) -> tuple[dict, dict]:
    dataset = tmp_path / "dataset.json"
    truth = tmp_path / "ground-truth.json"
    subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--sources",
            str(SOURCES),
            "--dataset",
            str(dataset),
            "--ground-truth",
            str(truth),
        ],
        check=True,
    )
    return json.loads(dataset.read_text(encoding="utf-8")), json.loads(truth.read_text(encoding="utf-8"))


def test_benchmark_is_exactly_10_10_10_and_ground_truth_does_not_leak(tmp_path: Path) -> None:
    raw, truth = _build(tmp_path)
    payload = ValidationDatasetPayload.model_validate(raw)
    assert payload.evidence_level == "synthetic"
    assert payload.automation_eligible is False
    assert len(payload.scenarios) == 30
    assert len({item.id for item in payload.scenarios}) == 30
    assert all(item.expected == [] for item in payload.scenarios)
    assert Counter(item["category"] for item in truth["scenarios"]) == {
        "public_record_baseline": 10,
        "public_record_mutation": 10,
        "synthetic_full_chain": 10,
    }
    assert {item.id for item in payload.scenarios} == {item["id"] for item in truth["scenarios"]}


def test_public_baselines_preserve_frozen_source_amounts_and_ocids(tmp_path: Path) -> None:
    raw, truth = _build(tmp_path)
    manifest = json.loads(SOURCES.read_text(encoding="utf-8"))
    source_by_id = {item["source_id"]: item for item in manifest["records"]}
    scenario_by_id = {item["id"]: item for item in raw["scenarios"]}
    baselines = [item for item in truth["scenarios"] if item["category"] == "public_record_baseline"]
    assert len(baselines) == 10
    for item in baselines:
        source = source_by_id[item["source_id"]]
        scenario = scenario_by_id[item["id"]]
        assert item["ocid"] == source["ocid"]
        assert item["expected"] == []
        assert item["mutation"] is None
        assert len(scenario["documents"]) == 1
        provenance = scenario["documents"][0]["content"]["_benchmark_provenance"]
        assert provenance["ocid"] == source["ocid"]
        assert provenance["source_amount"] == source["amount"]
        assert scenario["documents"][0]["content"]["lines"][0]["unit_price"] == source["amount"]


def test_each_public_mutation_has_one_declared_source_and_frozen_expected_result(tmp_path: Path) -> None:
    _, truth = _build(tmp_path)
    mutations = [item for item in truth["scenarios"] if item["category"] == "public_record_mutation"]
    assert len(mutations) == 10
    assert len({item["source_id"] for item in mutations}) == 10
    for item in mutations:
        assert item["expected"]
        assert item["mutation"]
        assert item["mutation_type"] in {
            "price_over_order",
            "invoiced_over_received",
            "discount_missing",
            "unmatched_invoice_line",
        }


def test_synthetic_cases_include_full_business_chain(tmp_path: Path) -> None:
    raw, truth = _build(tmp_path)
    category = {item["id"]: item["category"] for item in truth["scenarios"]}
    for scenario in raw["scenarios"]:
        if category[scenario["id"]] != "synthetic_full_chain":
            continue
        roles = {document["content"]["document_type"] for document in scenario["documents"]}
        assert {"proposal", "order", "confirmation", "delivery", "invoice", "payment"} <= roles
