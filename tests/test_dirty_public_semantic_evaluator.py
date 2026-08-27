from __future__ import annotations

from scripts.evaluate_dirty_public_semantics import evaluate_case, evaluate_lines


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


def test_unknown_fields_are_not_scored() -> None:
    truth = {"fields": {"document_type": "invoice"}}
    observed = {
        "document_type": "invoice",
        "number": "SOMETHING",
        "line_count": 0,
        "derived_subtotal": "0",
        "derived_tax": "0",
        "lines": [],
        "references": {},
    }
    result = evaluate_case(truth, observed)
    assert result["passed"] is True
    assert result["scored_fields"] == 1
    assert result["hallucinations"] == []


def test_explicit_null_truth_counts_hallucination() -> None:
    truth = {"expected_null_fields": ["number"]}
    observed = {
        "number": "DUTZ",
        "line_count": 0,
        "derived_subtotal": "0",
        "derived_tax": "0",
        "lines": [],
        "references": {},
    }
    result = evaluate_case(truth, observed)
    assert result["passed"] is False
    assert result["hallucinations"] == ["number"]


def test_abstention_satisfies_explicit_null_truth() -> None:
    truth = {"expected_null_fields": ["number"]}
    observed = {
        "number": None,
        "line_count": 0,
        "derived_subtotal": "0",
        "derived_tax": "0",
        "lines": [],
        "references": {},
    }
    result = evaluate_case(truth, observed)
    assert result["passed"] is True
    assert result["hallucinations"] == []
