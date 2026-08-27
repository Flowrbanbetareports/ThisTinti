#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
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
MAX_SOURCE_BYTES = 25 * 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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
        # The current parser API returns exactly one ParsedDocument and therefore
        # does not independently measure packet/document segmentation.
        "logical_document_count": parsed.metadata.get("logical_document_count_observed"),
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
        "complete_scope": complete,
        "precision_evaluable": complete,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "matched": matched,
    }


def evaluate_case(
    truth: dict[str, Any],
    observed: dict[str, Any],
    overridden_fields: set[str] | None = None,
) -> dict[str, Any]:
    overridden = set(overridden_fields or ())
    field_results: dict[str, bool] = {}
    unscored_overrides: list[str] = []
    hallucinations: list[str] = []

    for field, expected in (truth.get("fields") or {}).items():
        if field in overridden:
            unscored_overrides.append(field)
            continue
        field_results[field] = values_equal(expected, observed.get(field))
    for field in truth.get("expected_null_fields") or []:
        if field in overridden:
            unscored_overrides.append(field)
            continue
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
        True
        if "derived_tax" not in truth
        else decimal_text(truth["derived_tax"]) == decimal_text(observed["derived_tax"])
    )
    expected_lines = truth.get("lines") or []
    complete_line_scope = truth.get("line_scope") == "complete"
    line_metrics = evaluate_lines(expected_lines, observed["lines"], complete_line_scope)
    lines_passed = not expected_lines or (
        line_metrics["fn"] == 0 and (not complete_line_scope or line_metrics["fp"] == 0)
    )

    expected_document_count = truth.get("logical_document_count")
    observed_document_count = observed.get("logical_document_count")
    segmentation_evaluable = expected_document_count is not None and observed_document_count is not None
    segmentation_passed = (
        int(expected_document_count) == int(observed_document_count) if segmentation_evaluable else None
    )

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
    if segmentation_evaluable and segmentation_passed is False:
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
        "unscored_overrides": sorted(set(unscored_overrides)),
        "hallucinations": hallucinations,
        "minimum_lines_passed": minimum_lines_passed,
        "subtotal_passed": subtotal_passed,
        "tax_passed": tax_passed,
        "line_metrics": line_metrics,
        "segmentation_evaluable": segmentation_evaluable,
        "segmentation_passed": segmentation_passed,
        "segmentation_note": None if segmentation_evaluable else "not_measured_by_single_document_parser_contract",
    }


def empty_observation(message: str) -> dict[str, Any]:
    return {
        "document_type": None,
        "number": None,
        "document_date": None,
        "currency": None,
        "supplier_name": None,
        "supplier_vat": None,
        "references": {},
        "confidence": 0.0,
        "message": message,
        "line_count": 0,
        "derived_subtotal": "0",
        "derived_tax": "0",
        "lines": [],
        "recognition": {},
        "logical_document_count": None,
    }


def parse_case(
    path: Path, source: dict[str, Any], case_truth: dict[str, Any]
) -> tuple[str, dict[str, Any] | None, dict[str, Any], dict[str, Any]]:
    overrides = source.get("overrides") or {}
    overridden_fields = set(overrides)
    try:
        parsed = parse_file(path, source["filename"], source.get("content_type"), overrides)
        observed = normalize_observed(parsed)
        return "parsed", None, observed, evaluate_case(case_truth, observed, overridden_fields)
    except ParseError as exc:
        observed = empty_observation(str(exc))
        evaluation = evaluate_case(case_truth, observed, overridden_fields)
        evaluation["passed"] = False
        evaluation["failures"] = ["parse_error", *evaluation["failures"]]
        return "parse_error", {"code": exc.code, "message": str(exc)}, observed, evaluation


def source_integrity(source: dict[str, Any], payload: bytes) -> tuple[str | None, str, bool]:
    expected = source.get("sha256")
    observed = hashlib.sha256(payload).hexdigest()
    valid_expected = isinstance(expected, str) and SHA256_PATTERN.fullmatch(expected) is not None
    return expected if isinstance(expected, str) else None, observed, bool(valid_expected and observed == expected)


def summarize(
    cases: list[dict[str, Any]],
    frozen: bool,
    elapsed: float,
    *,
    integrity_failures: int = 0,
) -> dict[str, Any]:
    scored_fields = sum(case["evaluation"]["scored_fields"] for case in cases)
    correct_fields = sum(case["evaluation"]["correct_fields"] for case in cases)

    annotated_line_cases = [case for case in cases if case["evaluation"]["line_metrics"]["expected"] > 0]
    line_tp = sum(case["evaluation"]["line_metrics"]["tp"] for case in annotated_line_cases)
    line_fn = sum(case["evaluation"]["line_metrics"]["fn"] for case in annotated_line_cases)
    line_recall = line_tp / (line_tp + line_fn) if line_tp + line_fn else 1.0

    complete_line_cases = [
        case for case in annotated_line_cases if case["evaluation"]["line_metrics"]["complete_scope"]
    ]
    complete_tp = sum(case["evaluation"]["line_metrics"]["tp"] for case in complete_line_cases)
    complete_fp = sum(case["evaluation"]["line_metrics"]["fp"] for case in complete_line_cases)
    complete_fn = sum(case["evaluation"]["line_metrics"]["fn"] for case in complete_line_cases)
    line_precision = complete_tp / (complete_tp + complete_fp) if complete_tp + complete_fp else 1.0
    complete_recall = complete_tp / (complete_tp + complete_fn) if complete_tp + complete_fn else 1.0
    line_f1 = (
        2 * line_precision * complete_recall / (line_precision + complete_recall)
        if line_precision + complete_recall
        else 0.0
    )

    correct_conf = [case["observed"]["confidence"] for case in cases if case["evaluation"]["passed"]]
    incorrect_conf = [case["observed"]["confidence"] for case in cases if not case["evaluation"]["passed"]]
    segmentation_evaluable = sum(bool(case["evaluation"]["segmentation_evaluable"]) for case in cases)
    segmentation_passes = sum(
        case["evaluation"]["segmentation_passed"] is True
        for case in cases
        if case["evaluation"]["segmentation_evaluable"]
    )
    failed_cases = sum(not case["evaluation"]["passed"] for case in cases)
    unscored_override_count = sum(len(case["evaluation"].get("unscored_overrides") or []) for case in cases)
    gate_passed = bool(frozen and integrity_failures == 0 and cases and failed_cases == 0)
    return {
        "case_count": len(cases),
        "passed_cases": len(cases) - failed_cases,
        "failed_cases": failed_cases,
        "scored_fields": scored_fields,
        "correct_fields": correct_fields,
        "field_accuracy": correct_fields / scored_fields if scored_fields else 1.0,
        "unscored_override_fields": unscored_override_count,
        "line_tp": line_tp,
        "line_fn": line_fn,
        "line_recall": line_recall,
        "line_recall_scope_cases": len(annotated_line_cases),
        "line_precision_tp": complete_tp,
        "line_fp": complete_fp,
        "line_precision": line_precision,
        "line_f1": line_f1,
        "line_precision_scope_cases": len(complete_line_cases),
        "hallucination_count": sum(len(case["evaluation"]["hallucinations"]) for case in cases),
        "segmentation_evaluable": segmentation_evaluable,
        "segmentation_passes": segmentation_passes,
        "source_integrity_failures": integrity_failures,
        "mean_confidence_correct": sum(correct_conf) / len(correct_conf) if correct_conf else 0.0,
        "mean_confidence_incorrect": sum(incorrect_conf) / len(incorrect_conf) if incorrect_conf else 0.0,
        "gate_passed": gate_passed,
        "elapsed_seconds": round(elapsed, 3),
    }


def markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    rows = []
    for case in report["cases"]:
        result = "PASS" if case["evaluation"]["passed"] else "FAIL"
        rows.append(
            f"| {case['id']} | {case['observed']['document_type']} | "
            f"{case['observed']['number']} | {case['observed']['line_count']} | {result} |"
        )
    row_text = "\n".join(rows)
    gate = "PASS" if metrics["gate_passed"] else "FAIL"
    frozen = str(report["ground_truth"]["frozen"]).lower()
    return f"""# Dirty Public Corpus 22 — granular semantic evaluation

Generated: `{report["generated_at"]}`  
Engine: `{report["product"]["engine_version"]}`  
Ground truth frozen: **{frozen}**

## Metrics

- evaluated cases: **{metrics["case_count"]}**
- passed cases: **{metrics["passed_cases"]}**
- failed cases: **{metrics["failed_cases"]}**
- source-integrity failures: **{metrics["source_integrity_failures"]}**
- field accuracy: **{metrics["field_accuracy"]:.3f}** ({metrics["correct_fields"]}/{metrics["scored_fields"]})
- override-provided fields excluded from scoring: **{metrics["unscored_override_fields"]}**
- line precision, complete ground-truth scopes: **{metrics["line_precision"]:.3f}** ({metrics["line_precision_scope_cases"]} cases)
- line recall, all annotated expected lines: **{metrics["line_recall"]:.3f}** ({metrics["line_recall_scope_cases"]} cases)
- line F1, complete scopes only: **{metrics["line_f1"]:.3f}**
- hallucinated scored-null fields: **{metrics["hallucination_count"]}**
- independently measurable segmentation checks: **{metrics["segmentation_passes"]}/{metrics["segmentation_evaluable"]}**
- mean confidence, correct cases: **{metrics["mean_confidence_correct"]:.3f}**
- mean confidence, incorrect cases: **{metrics["mean_confidence_incorrect"]:.3f}**
- gate: **{gate}**

| Case | Type | Number | Lines | Result |
|---|---|---|---:|---|
{row_text}

## Interpretation

Only independently specified fields in the separate frozen ground truth are scored. Fields supplied to the parser through manifest overrides are explicitly excluded from accuracy. Missing ground truth is **unknown**, not a pass. Precision is reported only where line ground truth is declared complete; partial line annotations contribute to recall but cannot establish false-positive precision. The current single-document parser contract does not independently measure packet segmentation, so `logical_document_count: 1` is not counted as a segmentation success by itself. Every downloaded source must match its frozen SHA-256 before parsing. This remains a public/external robustness benchmark, not a real-company pilot or a universal accuracy claim.
"""


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    truth = load_json(args.truth)
    sources = {item["id"]: item for item in manifest.get("sources") or []}

    manifest_frozen = manifest.get("frozen") is True
    truth_frozen = truth.get("frozen") is True
    if not manifest_frozen or not truth_frozen:
        raise SystemExit("Semantic benchmark requires both manifest and ground truth to be frozen")
    if manifest.get("version") != truth.get("version"):
        raise SystemExit("Manifest and ground-truth versions differ")
    truth_cases = truth.get("cases") or {}
    if not truth_cases:
        raise SystemExit("Frozen semantic benchmark requires at least one ground-truth case")

    missing_sources = sorted(set(truth_cases) - set(sources))
    if missing_sources:
        raise SystemExit(f"Ground-truth cases missing from manifest: {missing_sources}")
    invalid_hashes = sorted(
        case_id
        for case_id in truth_cases
        if not isinstance(sources[case_id].get("sha256"), str)
        or SHA256_PATTERN.fullmatch(sources[case_id]["sha256"]) is None
    )
    if invalid_hashes:
        raise SystemExit(f"Frozen semantic cases require valid SHA-256 values: {invalid_hashes}")

    cases: list[dict[str, Any]] = []
    integrity_failures = 0
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="thistinti-dirty-semantics-") as temp_dir:
        workdir = Path(temp_dir)
        timeout = httpx.Timeout(90.0)
        headers = {"User-Agent": "ThisTinti-dirty-semantics/1.1"}
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            for case_id, case_truth in truth_cases.items():
                source = sources[case_id]
                response = client.get(source["url"])
                response.raise_for_status()
                payload = response.content
                if not payload:
                    raise SystemExit(f"Empty source response for {case_id}")
                if len(payload) > MAX_SOURCE_BYTES:
                    raise SystemExit(f"Source exceeds {MAX_SOURCE_BYTES} bytes: {case_id}")

                expected_sha, observed_sha, integrity_passed = source_integrity(source, payload)
                if not integrity_passed:
                    integrity_failures += 1
                    observed = empty_observation("Frozen source SHA-256 mismatch; parser not run")
                    evaluation = evaluate_case(case_truth, observed, set((source.get("overrides") or {}).keys()))
                    evaluation["passed"] = False
                    evaluation["failures"] = ["source_integrity", *evaluation["failures"]]
                    cases.append(
                        {
                            "id": case_id,
                            "expected_sha256": expected_sha,
                            "source_sha256": observed_sha,
                            "integrity_passed": False,
                            "parse_status": "not_run_integrity_failure",
                            "parse_error": None,
                            "observed": observed,
                            "evaluation": evaluation,
                        }
                    )
                    continue

                path = workdir / source["filename"]
                path.write_bytes(payload)
                parse_status, parse_error, observed, evaluation = parse_case(path, source, case_truth)
                cases.append(
                    {
                        "id": case_id,
                        "expected_sha256": expected_sha,
                        "source_sha256": observed_sha,
                        "integrity_passed": True,
                        "parse_status": parse_status,
                        "parse_error": parse_error,
                        "observed": observed,
                        "evaluation": evaluation,
                    }
                )

    metrics = summarize(cases, truth_frozen, time.perf_counter() - started, integrity_failures=integrity_failures)
    report = {
        "schema": "thistinti.dirty-public-semantic-result.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product": {"name": "ThisTinti", "engine_version": RELEASE_VERSION},
        "manifest": {
            "version": manifest.get("version"),
            "frozen": manifest_frozen,
            "real_company_pilot": False,
        },
        "ground_truth": {
            "version": truth.get("version"),
            "frozen": truth_frozen,
            "real_company_pilot": False,
        },
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
