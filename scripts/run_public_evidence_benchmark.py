#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Tenant, ValidationDataset  # noqa: E402
from app.schemas import ValidationDatasetPayload  # noqa: E402
from app.services.validation import run_validation_dataset  # noqa: E402
from app.version import RELEASE_VERSION  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the 30-case public-evidence benchmark.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1_score": round(f1, 6),
    }


def validate_contract(raw: dict[str, Any], truth: dict[str, Any]) -> ValidationDatasetPayload:
    input_payload = ValidationDatasetPayload.model_validate(raw)
    if input_payload.evidence_level != "synthetic" or input_payload.automation_eligible:
        raise ValueError("Benchmark must remain synthetic and never automation-eligible")
    if len(input_payload.scenarios) != 30 or any(item.expected for item in input_payload.scenarios):
        raise ValueError("Input must have 30 scenarios and contain no expected findings")
    truth_by_id = {item["id"]: item for item in truth["scenarios"]}
    ids = {item.id for item in input_payload.scenarios}
    if len(truth_by_id) != 30 or ids != set(truth_by_id):
        raise ValueError("Input and ground truth must have a 1:1 scenario mapping")
    counts = Counter(item["category"] for item in truth["scenarios"])
    if counts != {"public_record_baseline":10,"public_record_mutation":10,"synthetic_full_chain":10}:
        raise ValueError(f"Invalid benchmark category distribution: {dict(counts)}")
    merged = copy.deepcopy(raw)
    for scenario in merged["scenarios"]:
        scenario["expected"] = truth_by_id[scenario["id"]]["expected"]
    return ValidationDatasetPayload.model_validate(merged)


def markdown(report: dict[str, Any]) -> str:
    overall = report["metrics"]["overall"]
    rows = []
    for name, item in report["metrics"]["by_category"].items():
        rows.append(
            f"| {name} | {item['scenario_count']} | {item['true_positives']} | {item['false_positives']} | "
            f"{item['false_negatives']} | {item['precision']:.3f} | {item['recall']:.3f} | {item['f1_score']:.3f} |"
        )
    return f"""# Public Evidence Benchmark 30 — risultato\n\n"
Generated: `{report['generated_at']}`  \nEngine: `{report['product']['engine_version']}`\n\n"
## Evidenza\n\n"
Questo è un benchmark indipendente, non un pilot aziendale reale. I 10 casi pubblici sono rappresentazioni normalizzate di record Portland; i 10 casi mutati sono derivati controllati; gli ultimi 10 sono sintetici professionali. La ground truth è separata dall'input e viene usata solo dall'evaluator dopo l'ingestione.\n\n"
## Metriche\n\n"
- scenari: **{report['metrics']['scenario_count']}**\n"
- documenti: **{report['metrics']['document_count']}**\n"
- anomalie attese: **{report['metrics']['expected_finding_count']}**\n"
- TP / FP / FN: **{overall['true_positives']} / {overall['false_positives']} / {overall['false_negatives']}**\n"
- precisione: **{overall['precision']:.3f}**\n"
- recall: **{overall['recall']:.3f}**\n"
- F1: **{overall['f1_score']:.3f}**\n"
- MAE importi: **{report['metrics']['amount_mae']:.2f}**\n"
- gate: **{'PASS' if report['metrics']['gate_passed'] else 'FAIL'}**\n"
- tempo: **{report['metrics']['elapsed_seconds']:.3f} s**\n\n"
| Categoria | Scenari | TP | FP | FN | Precisione | Recall | F1 |\n"
|---|---:|---:|---:|---:|---:|---:|---:|\n"
{chr(10).join(rows)}\n\n"
## Integrità\n\n"
- SHA-256 input: `{report['integrity']['dataset_sha256']}`\n"
- SHA-256 ground truth: `{report['integrity']['ground_truth_sha256']}`\n"
- ground truth separata: **sì**\n"
- pilot reale completato: **no**\n"
"""


def main() -> int:
    args = parse_args()
    raw, truth = load(args.dataset), load(args.ground_truth)
    payload = validate_contract(raw, truth)
    truth_by_id = {item["id"]: item for item in truth["scenarios"]}
    db = SessionLocal()
    storage_path: Path | None = None
    try:
        tenant = Tenant(name="ThisTinti public evidence benchmark 30", status="active")
        db.add(tenant)
        db.flush()
        storage_path = settings.storage_dir / tenant.id
        dataset = ValidationDataset(
            tenant_id=tenant.id,
            name=payload.name,
            version=payload.version,
            description=payload.description,
            schema_json=json.dumps(raw, ensure_ascii=False, default=str),
        )
        db.add(dataset)
        db.flush()
        started = time.perf_counter()
        run = run_validation_dataset(db, dataset, payload, actor_id=None)
        elapsed = time.perf_counter() - started
        db.commit()
        details = json.loads(run.details_json or "{}")

        accum = defaultdict(lambda: {"scenario_count":0,"tp":0,"fp":0,"fn":0})
        results = []
        for result in details.get("scenarios", []):
            truth_item = truth_by_id[result["id"]]
            category = truth_item["category"]
            block = accum[category]
            block["scenario_count"] += 1
            block["tp"] += int(result.get("true_positives", 0))
            block["fp"] += len(result.get("false_positives", []))
            block["fn"] += len(result.get("false_negatives", []))
            results.append({
                **result,
                "category": category,
                "source_id": truth_item.get("source_id"),
                "ocid": truth_item.get("ocid"),
                "mutation_type": truth_item.get("mutation_type"),
            })
        by_category = {}
        for name in ("public_record_baseline", "public_record_mutation", "synthetic_full_chain"):
            item = accum[name]
            by_category[name] = {"scenario_count": item["scenario_count"], **metrics(item["tp"], item["fp"], item["fn"])}

        report = {
            "schema": "thistinti.public-evidence-benchmark-result.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "product": {"name":"ThisTinti","engine_version":RELEASE_VERSION},
            "classification": {
                "evidence_level":"synthetic",
                "contains_public_source_normalizations":True,
                "contains_controlled_mutations":True,
                "real_pilot_completed":False,
                "commercial_accuracy_claim_allowed":False,
                "automation_eligible":False,
            },
            "integrity": {
                "dataset_sha256":digest(args.dataset),
                "ground_truth_sha256":digest(args.ground_truth),
                "public_source_records":10,
                "controlled_mutations":10,
                "ground_truth_separate_from_input":True,
            },
            "metrics": {
                "scenario_count":len(payload.scenarios),
                "document_count":sum(len(item.documents) for item in payload.scenarios),
                "expected_finding_count":sum(len(item.expected) for item in payload.scenarios),
                "overall":metrics(int(run.true_positives or 0), int(run.false_positives or 0), int(run.false_negatives or 0)),
                "amount_mae":float(run.amount_mae or 0),
                "gate_passed":bool(run.gate_passed),
                "elapsed_seconds":round(elapsed,3),
                "average_seconds_per_scenario":round(elapsed / len(payload.scenarios),3),
                "by_category":by_category,
            },
            "scenario_results":results,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        args.markdown.write_text(markdown(report), encoding="utf-8")
        if run.status != "completed":
            raise SystemExit(f"Benchmark engine failed: {run.error_message}")
        if not run.gate_passed:
            raise SystemExit(f"Benchmark gate failed: precision={run.precision} recall={run.recall} f1={run.f1_score} mae={run.amount_mae}")
        return 0
    finally:
        db.close()
        if storage_path:
            shutil.rmtree(storage_path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
