#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.parsers import ParseError, parse_file  # noqa: E402
from app.version import RELEASE_VERSION  # noqa: E402

DEFAULT_MANIFEST = ROOT / "samples" / "dirty_public_corpus_22.json"
DEFAULT_TRUTH = ROOT / "samples" / "dirty_public_corpus_22_ground_truth.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate granular semantics on the dirty public corpus")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def decimal_text(value: Any) -> str:
    if value is None:
        return ""
    parsed = Decimal(str(value))
    if parsed == 0:
        return "0"
    return format(parsed.normalize(), "f")


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def normalize_observed(parsed: Any) -> dict[str, Any]:
    lines = []
    for line in parsed.lines:
        lines.append(
            {
                "sku": normalize_text(line.sku),
                "description": normalize_text(line.description),
                "quantity": decimal_text(line.quantity),
                "unit_price": decimal_text(line.unit_price),
                "tax_rate": decimal_text(line.tax_rate),
                "line_total": decimal_text(line.line_total),
                "confidence": float(line.confidence),
            }
        )
    subtotal = sum((Decimal(item["line_total"] or "0") for item in lines), Decimal("0"))
    tax = sum(
        (Decimal(item["line_total"] or "0") * Decimal(item["tax_rate"] or "0") / Decimal("100") for item in lines),
        Decimal("0"),
    )
    return {
        "document_type": parsed.document_type,
        "number": parsed.number,
        "document_date": None if parsed.document_date is None else str(parsed.document_date),
        "currency": parsed.currency,
        "supplier_name": normalize_text(parsed.supplier_name),
        "supplier_vat": normalize_text(parsed.supplier_vat),
        "references": parsed.references,
        "confidence": float(parsed.confidence),
        "message": parsed.message,
        "line_count": len(lines),
        "derived_subtotal": decimal_text(subtotal),
        "derived_tax": decimal_text(tax),
        "lines": lines,
        "recognition": {
            "document_number": parsed.metadata.get("document_number_recognition"),
            "currency": parsed.metadata.get("currency_recognition"),
        },
    }


def values_equal(expected: Any, observed: Any) -> bool:
    if expected is None or observed is None:
        return expected is observed
    if isinstance(expected, (int, float)):
        return decimal_text(expected) == decimal_text(observed)
    return normalize_text(expected) == normalize_text(observed)


def line_matches(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    for key in ("sku", "quantity", "unit_price", "tax_rate", "line_total"):
        if key in expected and not values_equal(expected[key], observed.get(key)):
            return False
    needle = expected.get("description_contains")
    if needle and str(needle).casefold() not in str(observed.get("description") or "").casefold():
        return False
    return True


def evaluate_lines(expected: list[dict[str, Any]], observed: list[dict[str, Any]], complete: bool) -> dict[str, Any]:
    remaining = set(range(len(observed)))
    matched: list[tuple[int, int]] = []
    for expected_index, expected_line in enumerate(expected):
        selected = None
        for observed_index in sorted(remaining):
            if line_matches(expected_line, observed[observed_index]):
                selected = observed_index
                break
        if selected is not None:
            remaining.remove(selected)
            matched.append((expected_index, selected))
    tp = len(matched)
    fn = len(expected) - tp
    fp = len(remaining) if complete else 0
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "expected": len(expected),
        "observed": len(observed),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "matched": matched,
    }


def evaluate_case(truth: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    field_results: dict[str, bool] = {}
    hallucinations: list[str] = []
    for field, expected in (truth.get("fields") or {}).items():
        field_results[field] = values_equal(expected, observed.get(field))
    for field in truth.get("expected_null_fields") or []:
        observed_value = observed.get(field)
        field_results[field] = observed_value in {None, "", "UNK"}
        if not field_results[field]:
            hallucinations.append(field)

    reference_results: dict[str, bool] = {}
    for key, expected_values in (truth.get("references") or {}).items():
        actual_values = (observed.get("references") or {}).get(key) or []
        reference_results[key] = set(map(str, actual_values)) == set(map(str, expected_values))

    minimum_lines = truth.get("minimum_lines")
    minimum_lines_passed = True if minimum_lines is None else observed["line_count"] >= int(minimum_lines)
    subtotal_passed = (
        True
        if "derived_subtotal" not in truth
        else decimal_text(truth["derived_subtotal"]) == decimal_text(observed["derived_subtotal"])
    )
    tax_passed = (
        True if "derived_tax" not in truth else decimal_text(truth["derived_tax"]) == decimal_text(observed["derived_tax"])
    )
    expected_lines = truth.get("lines") or []
    line_metrics = evaluate_lines(expected_lines, observed["lines"], truth.get("line_scope") == "complete")
    lines_passed = not expected_lines or (line_metrics["fn"] == 0 and line_metrics["fp"] == 0)

    logical_document_count = truth.get("logical_document_count")
    segmentation_evaluable = logical_document_count is not None
    segmentation_passed = True if logical_document_count is None else int(logical_document_count) == 1

    failures: list[str] = []
    failures.extend(f"field:{key}" for key, passed in field_results.items() if not passed)
    failures.extend(f"reference:{key}" for key, passed in reference_results.items() if not passed)
    if not minimum_lines_passed:
        failures.append("minimum_lines")
    if not subtotal_passed:
        failures.append("derived_subtotal")
    if not tax_passed:
        failures.append("derived_tax")
    if not lines_passed:
        failures.append("line_items")
    if segmentation_evaluable and not segmentation_passed:
        failures.append("segmentation")

    scored_fields = len(field_results) + len(reference_results)
    correct_fields = sum(field_results.values()) + sum(reference_results.values())
    return {
        "passed": not failures,
        "failures": failures,
        "field_results": field_results,
        "reference_results": reference_results,
        "scored_fields": scored_fields,
        "correct_fields": correct_fields,
        "hallucinations": hallucinations,
        "minimum_lines_passed": minimum_lines_passed,
        "subtotal_passed": subtotal_passed,
        "tax_passed": tax_passed,
        "line_metrics": line_metrics,
        "segmentation_evaluable": segmentation_evaluable,
        "segmentation_passed": segmentation_passed,
    }


def markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    rows = []
    for case in report["cases"]:
        result = "PASS" if case["evaluation"]["passed"] else "FAIL"
        rows.append(
            f"| {case['id']} | {case['observed']['document_type']} | {case['observed']['number']} | "
            f"{case['observed']['line_count']} | {result} |"
        )
    row_text = "\n".join(rows)
    return f"""# Dirty Public Corpus 22 — granular semantic evaluation

Generated: `{report['generated_at']}`  
Engine: `{report['product']['engine_version']}`  
Ground truth frozen: **{str(report['ground_truth']['frozen']).lower()}**

## Metrics

- evaluated cases: **{metrics['case_count']}**
- passed cases: **{metrics['passed_cases']}**
- failed cases: **{metrics['failed_cases']}**
- field accuracy: **{metrics['field_accuracy']:.3f}** ({metrics['correct_fields']}/{metrics['scored_fields']})
- line precision: **{metrics['line_precision']:.3f}**
- line recall: **{metrics['line_recall']:.3f}**
- line F1: **{metrics['line_f1']:.3f}**
- hallucinated scored-null fields: **{metrics['hallucination_count']}**
- segmentation checks passed: **{metrics['segmentation_passes']}/{metrics['segmentation_evaluable']}**
- mean confidence, correct cases: **{metrics['mean_confidence_correct']:.3f}**
- mean confidence, incorrect cases: **{metrics['mean_confidence_incorrect']:.3f}**
- gate: **{'PASS' if metrics['gate_passed'] else 'FAIL'}**

| Case | Type | Number | Lines | Result |
|---|---|---|---:|---|
{row_text}

## Interpretation

Only fields explicitly present in the separate ground-truth file are scored. Missing ground truth is **unknown**, not a pass. An abstention is preferred over a fabricated value when the truth explicitly requires null. This is not a real-company pilot and is not a universal accuracy claim.
"""


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    truth = load_json(args.truth)
    sources = {item["id"]: item for item in manifest["sources"]}
    cases: list[dict[str, Any]] = []
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="thistinti-dirty-semantics-") as temp_dir:
        workdir = Path(temp_dir)
        with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(90.0), headers={"User-Agent": "ThisTinti-dirty-semantics/1.0"}) as client:
            for case_id, case_truth in truth["cases"].items():
                source = sources.get(case_id)
                if source is None:
                    raise SystemExit(f"Ground-truth case missing from manifest: {case_id}")
                response = client.get(source["url"])
                response.raise_for_status()
                payload = response.content
                path = workdir / source["filename"]
                path.write_bytes(payload)
                try:
                    parsed = parse_file(path, source["filename"], source.get("content_type"), source.get("overrides") or {})
                    observed = normalize_observed(parsed)
                    evaluation = evaluate_case(case_truth, observed)
                    parse_status = "parsed"
                    parse_error = None
                except ParseError as exc:
                    observed = {
                        "document_type": None,
                        "number": None,
                        "document_date": None,
                        "currency": None,
                        "supplier_name": None,
                        "supplier_vat": None,
                        "references": {},
                        "confidence": 0.0,
                        "message": str(exc),
                        "line_count": 0,
                        "derived_subtotal": "0",
                        "derived_tax": "0",
                        "lines": [],
                        "recognition": {},
                    }
                    evaluation = {"passed": False, "failures": ["parse_error"], "field_results": {}, "reference_results": {}, "scored_fields": 0, "correct_fields": 0, "hallucinations": [], "minimum_lines_passed": False, "subtotal_passed": False, "tax_passed": False, "line_metrics": {"expected": len(case_truth.get("lines") or []), "observed": 0, "tp": 0, "fp": 0, "fn": len(case_truth.get("lines") or []), "precision": 0.0, "recall": 0.0, "f1": 0.0, "matched": []}, "segmentation_evaluable": case_truth.get("logical_document_count") is not None, "segmentation_passed": False}
                    parse_status = "parse_error"
                    parse_error = {"code": exc.code, "message": str(exc)}
                cases.append({"id": case_id, "source_sha256": hashlib.sha256(payload).hexdigest(), "parse_status": parse_status, "parse_error": parse_error, "observed": observed, "evaluation": evaluation})

    scored_fields = sum(case["evaluation"]["scored_fields"] for case in cases)
    correct_fields = sum(case["evaluation"]["correct_fields"] for case in cases)
    line_tp = sum(case["evaluation"]["line_metrics"]["tp"] for case in cases)
    line_fp = sum(case["evaluation"]["line_metrics"]["fp"] for case in cases)
    line_fn = sum(case["evaluation"]["line_metrics"]["fn"] for case in cases)
    line_precision = line_tp / (line_tp + line_fp) if line_tp + line_fp else 1.0
    line_recall = line_tp / (line_tp + line_fn) if line_tp + line_fn else 1.0
    line_f1 = 2 * line_precision * line_recall / (line_precision + line_recall) if line_precision + line_recall else 0.0
    correct_conf = [case["observed"]["confidence"] for case in cases if case["evaluation"]["passed"]]
    incorrect_conf = [case["observed"]["confidence"] for case in cases if not case["evaluation"]["passed"]]
    mean_correct = sum(correct_conf) / len(correct_conf) if correct_conf else 0.0
    mean_incorrect = sum(incorrect_conf) / len(incorrect_conf) if incorrect_conf else 0.0
    segmentation_evaluable = sum(case["evaluation"]["segmentation_evaluable"] for case in cases)
    segmentation_passes = sum(case["evaluation"]["segmentation_passed"] for case in cases if case["evaluation"]["segmentation_evaluable"])
    failed_cases = sum(not case["evaluation"]["passed"] for case in cases)
    frozen = bool(truth.get("frozen"))

    metrics = {
        "case_count": len(cases),
        "passed_cases": len(cases) - failed_cases,
        "failed_cases": failed_cases,
        "scored_fields": scored_fields,
        "correct_fields": correct_fields,
        "field_accuracy": correct_fields / scored_fields if scored_fields else 1.0,
        "line_tp": line_tp,
        "line_fp": line_fp,
        "line_fn": line_fn,
        "line_precision": line_precision,
        "line_recall": line_recall,
        "line_f1": line_f1,
        "hallucination_count": sum(len(case["evaluation"]["hallucinations"]) for case in cases),
        "segmentation_evaluable": segmentation_evaluable,
        "segmentation_passes": segmentation_passes,
        "mean_confidence_correct": mean_correct,
        "mean_confidence_incorrect": mean_incorrect,
        "gate_passed": not frozen or failed_cases == 0,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    report = {
        "schema": "thistinti.dirty-public-semantic-result.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product": {"name": "ThisTinti", "engine_version": RELEASE_VERSION},
        "ground_truth": {"version": truth.get("version"), "frozen": frozen, "real_company_pilot": False},
        "metrics": metrics,
        "cases": cases,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if metrics["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
