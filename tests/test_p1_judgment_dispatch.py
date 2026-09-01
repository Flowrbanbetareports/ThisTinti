from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import judgment_provenance


P1_RULE_CONTRACTS = (
    ("duplicate_document_number", "builtin:duplicate_document_number"),
    ("currency_mismatch", "builtin:currency_mismatch"),
    ("delivered_over_order", "builtin:delivered_over_order"),
    ("invoiced_over_received", "builtin:invoiced_over_received"),
    ("payment_over_invoice", "builtin:payment_over_invoice"),
    ("payment_without_invoice", "builtin:payment_without_invoice"),
)


@pytest.mark.parametrize(("case_type", "expected_rule_id"), P1_RULE_CONTRACTS)
def test_p1_judgment_dispatch_rejects_substituted_rule_identity(
    monkeypatch,
    case_type: str,
    expected_rule_id: str,
) -> None:
    def must_not_run(*args, **kwargs):
        raise AssertionError("current-support matcher must not run for a substituted rule identity")

    monkeypatch.setitem(
        judgment_provenance._P1_RULE_MATCHERS,
        case_type,
        (expected_rule_id, must_not_run),
    )
    finding = SimpleNamespace(rule_id="builtin:substituted_rule")

    assert not judgment_provenance._finding_matches_case_contract(
        None,
        case_type=case_type,
        finding=finding,
    )


@pytest.mark.parametrize(("case_type", "expected_rule_id"), P1_RULE_CONTRACTS)
def test_p1_judgment_dispatch_invokes_only_the_exact_case_matcher(
    monkeypatch,
    case_type: str,
    expected_rule_id: str,
) -> None:
    sentinel_db = object()
    finding = SimpleNamespace(rule_id=expected_rule_id)
    calls: list[tuple[object, object]] = []

    def current_support(db, *, finding):
        calls.append((db, finding))
        return True

    monkeypatch.setitem(
        judgment_provenance._P1_RULE_MATCHERS,
        case_type,
        (expected_rule_id, current_support),
    )
    monkeypatch.setattr(
        judgment_provenance,
        "finding_document_evidence_bytes_are_current",
        lambda db, *, finding: True,
    )

    assert judgment_provenance._finding_matches_case_contract(
        sentinel_db,
        case_type=case_type,
        finding=finding,
    )
    assert calls == [(sentinel_db, finding)]


def test_judgment_dispatch_rejects_unqualified_case_type() -> None:
    finding = SimpleNamespace(rule_id="builtin:unmatched_invoice_line")

    assert not judgment_provenance._finding_matches_case_contract(
        None,
        case_type="unmatched_invoice_line",
        finding=finding,
    )
