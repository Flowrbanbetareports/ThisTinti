from __future__ import annotations

from scripts.evaluate_dirty_public_semantics import evaluate_case, evaluate_lines, source_integrity, summarize


def _observed(**values):
    base = {
        "document_type": None,
        "number": None,
        "line_count": 0,
        "derived_subtotal": "0",
        "derived_tax": "0",
        "lines": [],
        "references": {},
        "confidence": 0.5,
        "logical_document_count": None,
    }
    base.update(values)
    return base


def test_line_metrics_count_false_positive_and_false_negative() -> None:
    expected = [
        {"sku": "A", "quantity": "1", "unit_price": "10"},
        {"sku": "B", "quantity": "2", "unit_price": "5"},
    ]
    observed = [
        {"sku": "A", "quantity": "1", "unit_price": "10", "tax_rate": "0", "line_total": "10", "description": None},
        {"sku": "X", "quantity": "1", "unit_price": "99", "tax_rate": "0", "line_total": "99", "description": None},
    ]
    metrics = evaluate_lines(expected, observed, complete=True)
    assert metrics["tp"] == 1
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["precision_evaluable"] is True


def test_partial_line_truth_does_not_claim_false_positive_precision() -> None:
    expected = [{"sku": "A", "quantity": "1", "unit_price": "10"}]
    observed = [
        {"sku": "A", "quantity": "1", "unit_price": "10", "tax_rate": "0", "line_total": "10", "description": None},
        {"sku": "B", "quantity": "1", "unit_price": "20", "tax_rate": "0", "line_total": "20", "description": None},
    ]
    metrics = evaluate_lines(expected, observed, complete=False)
    assert metrics["tp"] == 1
    assert metrics["fp"] == 0
    assert metrics["precision_evaluable"] is False


def test_unknown_fields_are_not_scored() -> None:
    result = evaluate_case({"fields": {"document_type": "invoice"}}, _observed(document_type="invoice", number="SOMETHING"))
    assert result["passed"] is True
    assert result["scored_fields"] == 1
    assert result["hallucinations"] == []


def test_override_provided_field_is_not_scored_as_parser_accuracy() -> None:
    truth = {"fields": {"document_type": "proposal", "number": "Q-1"}}
    observed = _observed(document_type="proposal", number="Q-1")
    result = evaluate_case(truth, observed, {"document_type"})
    assert result["passed"] is True
    assert result["scored_fields"] == 1
    assert result["field_results"] == {"number": True}
    assert result["unscored_overrides"] == ["document_type"]


def test_explicit_null_truth_counts_hallucination() -> None:
    result = evaluate_case({"expected_null_fields": ["number"]}, _observed(number="DUTZ"))
    assert result["passed"] is False
    assert result["hallucinations"] == ["number"]


def test_abstention_satisfies_explicit_null_truth() -> None:
    result = evaluate_case({"expected_null_fields": ["number"]}, _observed(number=None))
    assert result["passed"] is True
    assert result["hallucinations"] == []


def test_expected_single_document_is_not_fake_segmentation_measurement() -> None:
    result = evaluate_case({"logical_document_count": 1}, _observed(logical_document_count=None))
    assert result["passed"] is True
    assert result["segmentation_evaluable"] is False
    assert result["segmentation_passed"] is None
    assert result["segmentation_note"] == "not_measured_by_single_document_parser_contract"


def test_source_integrity_requires_exact_frozen_sha() -> None:
    payload = b"frozen-source"
    expected, observed, passed = source_integrity({"sha256": "0" * 64}, payload)
    assert expected == "0" * 64
    assert observed != expected
    assert passed is False


def test_summary_gate_fails_open_truth_or_integrity_failure() -> None:
    case = {
        "observed": _observed(),
        "evaluation": evaluate_case({}, _observed()),
    }
    assert summarize([case], False, 0.1)["gate_passed"] is False
    assert summarize([case], True, 0.1, integrity_failures=1)["gate_passed"] is False
    assert summarize([case], True, 0.1, integrity_failures=0)["gate_passed"] is True
