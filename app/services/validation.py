from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DiscrepancyCase, Tenant, ValidationDataset, ValidationRun, utcnow
from ..schemas import ValidationDatasetPayload, ValidationExpectedFinding
from ..version import RELEASE_VERSION
from .ingestion import ingest_path

ENGINE_VERSION = RELEASE_VERSION


@dataclass
class MatchResult:
    expected_index: int
    found_index: int
    case_type: str
    expected_amount: float | None
    found_amount: float
    amount_error: float | None


def _amount_matches(expected: ValidationExpectedFinding, found_amount: float) -> bool:
    if expected.amount is None:
        return True
    tolerance = max(expected.absolute_tolerance, abs(expected.amount) * expected.amount_tolerance)
    return abs(found_amount - expected.amount) <= tolerance


def _compare_findings(
    expected: list[ValidationExpectedFinding], found: list[dict[str, Any]], ignored: set[str]
) -> dict:
    unmatched_found = set(range(len(found)))
    matches: list[MatchResult] = []
    false_negatives: list[dict[str, Any]] = []

    for expected_index, item in enumerate(expected):
        candidates: list[tuple[float, int]] = []
        for found_index in unmatched_found:
            candidate = found[found_index]
            if candidate["case_type"] != item.case_type:
                continue
            if not _amount_matches(item, candidate["amount"]):
                continue
            distance = 0.0 if item.amount is None else abs(candidate["amount"] - item.amount)
            candidates.append((distance, found_index))
        if not candidates:
            false_negatives.append(item.model_dump())
            continue
        _, chosen = min(candidates, key=lambda entry: (entry[0], entry[1]))
        unmatched_found.remove(chosen)
        candidate = found[chosen]
        amount_error = None if item.amount is None else abs(candidate["amount"] - item.amount)
        matches.append(
            MatchResult(
                expected_index=expected_index,
                found_index=chosen,
                case_type=item.case_type,
                expected_amount=item.amount,
                found_amount=candidate["amount"],
                amount_error=amount_error,
            )
        )

    false_positives = [found[index] for index in sorted(unmatched_found) if found[index]["case_type"] not in ignored]
    amount_errors = [match.amount_error for match in matches if match.amount_error is not None]
    return {
        "matches": [asdict(match) for match in matches],
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_positives": len(matches),
        "amount_errors": amount_errors,
        "passed": not false_positives and not false_negatives,
    }


def run_validation_dataset(
    db: Session,
    dataset: ValidationDataset,
    payload: ValidationDatasetPayload,
    actor_id: str | None,
) -> ValidationRun:
    dataset.automation_eligible = False
    run = ValidationRun(
        tenant_id=dataset.tenant_id,
        dataset_id=dataset.id,
        status="running",
        engine_version=ENGINE_VERSION,
        scenario_count=len(payload.scenarios),
        created_by=actor_id,
    )
    db.add(run)
    db.flush()

    total_tp = total_fp = total_fn = 0
    all_amount_errors: list[float] = []
    scenario_results: list[dict[str, Any]] = []

    try:
        for scenario in payload.scenarios:
            savepoint = db.begin_nested()
            storage_path: Path | None = None
            try:
                temp_tenant = Tenant(name=f"Validation:{run.id}:{scenario.id}", status="active")
                db.add(temp_tenant)
                db.flush()
                storage_path = settings.storage_dir / temp_tenant.id

                parse_failures: list[dict[str, str]] = []
                with tempfile.TemporaryDirectory(prefix="thistinti-validation-") as directory:
                    root = Path(directory)
                    for index, document in enumerate(scenario.documents, start=1):
                        safe_filename = Path(document.filename).name or f"document-{index}.json"
                        if not safe_filename.lower().endswith(".json"):
                            safe_filename = f"{safe_filename}.json"
                        source = root / f"{index:03d}-{safe_filename}"
                        source.write_text(
                            json.dumps(document.content, ensure_ascii=False, indent=2, default=str),
                            encoding="utf-8",
                        )
                        parsed, outcome = ingest_path(
                            db,
                            temp_tenant.id,
                            source,
                            safe_filename,
                            document.mime_type,
                            {},
                        )
                        if outcome == "parse_failed":
                            parse_failures.append(
                                {
                                    "filename": safe_filename,
                                    "message": parsed.parse_message or "parse_failed",
                                }
                            )

                cases = list(
                    db.scalars(
                        select(DiscrepancyCase).where(
                            DiscrepancyCase.tenant_id == temp_tenant.id,
                            DiscrepancyCase.status.in_(["open", "needs_review", "confirmed"]),
                        )
                    )
                )
                found = sorted(
                    [
                        {
                            "case_type": case.case_type,
                            "amount": float(case.amount_estimate),
                            "confidence": case.confidence,
                            "severity": case.severity,
                            "title": case.title,
                        }
                        for case in cases
                    ],
                    key=lambda item: (item["case_type"], item["amount"], item["title"]),
                )
                comparison = _compare_findings(
                    scenario.expected,
                    found,
                    set(scenario.ignore_unexpected_types),
                )
                if parse_failures:
                    comparison["passed"] = False
                total_tp += comparison["true_positives"]
                total_fp += len(comparison["false_positives"])
                total_fn += len(comparison["false_negatives"])
                all_amount_errors.extend(comparison.pop("amount_errors"))
                scenario_results.append(
                    {
                        "id": scenario.id,
                        "description": scenario.description,
                        "expected_count": len(scenario.expected),
                        "found_count": len(found),
                        "found": found,
                        "parse_failures": parse_failures,
                        **comparison,
                    }
                )
            except Exception as exc:  # scenario isolation is intentional
                total_fn += len(scenario.expected)
                scenario_results.append(
                    {
                        "id": scenario.id,
                        "description": scenario.description,
                        "expected_count": len(scenario.expected),
                        "found_count": 0,
                        "found": [],
                        "matches": [],
                        "false_positives": [],
                        "false_negatives": [item.model_dump() for item in scenario.expected],
                        "parse_failures": [],
                        "passed": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            finally:
                savepoint.rollback()
                if storage_path:
                    shutil.rmtree(storage_path, ignore_errors=True)

        precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 1.0
        recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        amount_mae = sum(all_amount_errors) / len(all_amount_errors) if all_amount_errors else 0.0
        all_scenarios_pass = all(result.get("passed", False) for result in scenario_results)
        gate = payload.gate
        gate_passed = (
            precision >= gate.min_precision
            and recall >= gate.min_recall
            and f1 >= gate.min_f1
            and amount_mae <= gate.max_amount_mae
            and (all_scenarios_pass if gate.require_all_scenarios_pass else True)
        )

        run.status = "completed"
        run.true_positives = total_tp
        run.false_positives = total_fp
        run.false_negatives = total_fn
        run.precision = round(precision, 6)
        run.recall = round(recall, 6)
        run.f1_score = round(f1, 6)
        run.amount_mae = round(amount_mae, 2)
        run.gate_passed = gate_passed
        run.details_json = json.dumps(
            {
                "gate": gate.model_dump(),
                "all_scenarios_pass": all_scenarios_pass,
                "scenarios": scenario_results,
            },
            ensure_ascii=False,
            default=str,
        )
        run.completed_at = utcnow()
        db.flush()
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_message = f"{type(exc).__name__}: {exc}"
        run.completed_at = utcnow()
        db.flush()
        return run
