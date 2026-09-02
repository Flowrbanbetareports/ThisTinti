from __future__ import annotations

import os
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import select, update

import app.legacy_cases_api as legacy_cases_api
from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, DocumentLine, ReviewDecision
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment
from tests.test_duplicate_number_finding_provenance import _upload as _upload_duplicate
from tests.test_provenance_currency_mismatch import _upload_json as _upload_currency
from tests.test_provenance_delivered_over_order import _upload_overdelivery
from tests.test_provenance_invoiced_over_received import _upload_overinvoice
from tests.test_provenance_payment_over_invoice import _upload_overpayment
from tests.test_provenance_payment_without_invoice import _upload as _upload_payment_without_invoice


pytestmark = pytest.mark.skipif(
    not os.getenv("THISTINTI_TEST_POSTGRES_URL"),
    reason="requires a real PostgreSQL database via THISTINTI_TEST_POSTGRES_URL",
)

P1_RULES = (
    "duplicate_document_number",
    "currency_mismatch",
    "delivered_over_order",
    "invoiced_over_received",
    "payment_over_invoice",
    "payment_without_invoice",
)


def _current_case_and_finding(case_type: str) -> tuple[str, str, str]:
    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == case_type))
        assert case is not None
        finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert finding is not None
        return case.id, finding.id, case.status


def _prepare_p1_case(client, auth, *, case_type: str, suffix: str) -> dict[str, str]:
    if case_type == "duplicate_document_number":
        number = f"DUP-{suffix}"
        first = _upload_duplicate(
            client,
            auth,
            filename=f"duplicate-{suffix.lower()}-a.json",
            source_number=number,
            suffix=f"{suffix}-A",
        )
        second = _upload_duplicate(
            client,
            auth,
            filename=f"duplicate-{suffix.lower()}-b.json",
            source_number=number,
            suffix=f"{suffix}-B",
        )
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        return {"document_id": second.json()["document"]["id"]}

    if case_type == "currency_mismatch":
        order_number = f"PO-CURRENCY-{suffix}"
        order = _upload_currency(
            client,
            auth,
            document_type="order",
            number=order_number,
            currency="EUR",
        )
        invoice = _upload_currency(
            client,
            auth,
            document_type="invoice",
            number=f"INV-CURRENCY-{suffix}",
            currency="USD",
            order_number=order_number,
        )
        assert order.status_code == 201, order.text
        assert invoice.status_code == 201, invoice.text
        return {"document_id": invoice.json()["document"]["id"]}

    if case_type == "delivered_over_order":
        _order_id, delivery_id = _upload_overdelivery(
            client,
            auth,
            suffix=suffix,
            ordered="10",
            delivered="12",
        )
        return {"document_id": delivery_id}

    if case_type == "invoiced_over_received":
        _upload_overinvoice(
            client,
            auth,
            suffix=suffix,
            received="10",
            invoiced="12",
        )
        return {"document_number": f"INV-PROV-{suffix}"}

    if case_type == "payment_over_invoice":
        _upload_overpayment(
            client,
            auth,
            suffix=suffix,
            invoice_total="100.00",
            payment_total="125.00",
        )
        return {"document_number": f"PAY-PROV-{suffix}"}

    if case_type == "payment_without_invoice":
        payment = _upload_payment_without_invoice(
            client,
            auth,
            number=f"PAY-WITHOUT-INV-{suffix}",
            total="125.00",
        )
        assert payment.status_code == 201, payment.text
        return {"document_id": payment.json()["document"]["id"]}

    raise AssertionError(f"unsupported P1 case type: {case_type}")


def _mutate_support(case_type: str, context: dict[str, str]) -> None:
    with SessionLocal() as mutator, mutator.begin():
        mutator.connection().exec_driver_sql("SET LOCAL lock_timeout = '3s'")

        if case_type == "duplicate_document_number":
            mutator.execute(
                update(Document)
                .where(Document.id == context["document_id"])
                .values(number="DUP-CORRECTED-AFTER-JUDGMENT")
            )
            return

        if case_type == "currency_mismatch":
            mutator.execute(
                update(Document)
                .where(Document.id == context["document_id"])
                .values(currency="EUR")
            )
            return

        if case_type == "delivered_over_order":
            mutator.execute(
                update(DocumentLine)
                .where(
                    DocumentLine.document_id == context["document_id"],
                    DocumentLine.line_no == 1,
                )
                .values(quantity=Decimal("8"))
            )
            return

        if case_type == "invoiced_over_received":
            mutator.execute(
                update(DocumentLine)
                .where(
                    DocumentLine.document_id
                    == select(Document.id).where(Document.number == context["document_number"]).scalar_subquery(),
                    DocumentLine.line_no == 1,
                )
                .values(quantity=Decimal("8"))
            )
            return

        if case_type == "payment_over_invoice":
            mutator.execute(
                update(DocumentLine)
                .where(
                    DocumentLine.document_id
                    == select(Document.id).where(Document.number == context["document_number"]).scalar_subquery(),
                    DocumentLine.line_no == 1,
                )
                .values(line_total=Decimal("90.00"))
            )
            return

        if case_type == "payment_without_invoice":
            mutator.execute(
                update(Document)
                .where(Document.id == context["document_id"])
                .values(parse_status="failed")
            )
            return

        raise AssertionError(f"unsupported P1 case type: {case_type}")


@pytest.mark.parametrize("case_type", P1_RULES)
def test_real_judgment_first_serializes_mutation_and_becomes_stale_afterward(
    client,
    auth,
    monkeypatch,
    case_type,
):
    """Every P1 rule serializes a real judgment before a material support mutation."""
    context = _prepare_p1_case(
        client,
        auth,
        case_type=case_type,
        suffix=f"PG-JUDGMENT-FIRST-{case_type.upper()}",
    )
    case_id, finding_id, _initial_status = _current_case_and_finding(case_type)

    judgment_flushed = threading.Event()
    allow_judgment_commit = threading.Event()
    mutation_started = threading.Event()
    mutation_finished = threading.Event()
    judgment_errors: list[BaseException] = []
    mutation_errors: list[BaseException] = []
    judgment_status: list[int] = []

    original_record = legacy_cases_api.record_judgment_provenance

    def record_then_pause(*args, **kwargs):
        judgment = original_record(*args, **kwargs)
        assert judgment is not None
        judgment_flushed.set()
        assert allow_judgment_commit.wait(timeout=3.0)
        return judgment

    monkeypatch.setattr(legacy_cases_api, "record_judgment_provenance", record_then_pause)

    def persist_judgment() -> None:
        try:
            response = client.post(
                f"/api/cases/{case_id}/decision",
                headers=auth,
                json={
                    "decision": "confirmed",
                    "note": f"Judgment-first PostgreSQL qualification evidence for {case_type}.",
                },
            )
            judgment_status.append(response.status_code)
            assert response.status_code == 200, response.text
        except BaseException as exc:
            judgment_errors.append(exc)

    def mutate_support() -> None:
        try:
            mutation_started.set()
            _mutate_support(case_type, context)
        except BaseException as exc:
            mutation_errors.append(exc)
        finally:
            mutation_finished.set()

    judgment_worker = threading.Thread(target=persist_judgment, daemon=True)
    judgment_worker.start()
    assert judgment_flushed.wait(timeout=2.0)

    mutation_worker = threading.Thread(target=mutate_support, daemon=True)
    mutation_worker.start()
    assert mutation_started.wait(timeout=1.0)
    time.sleep(0.35)
    assert not mutation_finished.is_set(), f"{case_type} support mutation must block behind the judgment transaction"

    allow_judgment_commit.set()
    judgment_worker.join(timeout=3.0)
    mutation_worker.join(timeout=3.0)

    assert not judgment_worker.is_alive()
    assert not mutation_worker.is_alive()
    assert not judgment_errors
    assert not mutation_errors
    assert judgment_status == [200]
    assert mutation_finished.is_set()

    # The historic judgment remains persisted, but a subsequent production-path
    # decision must fail closed because the finding no longer has exact-current support.
    reviewed_again = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={
            "decision": "dismissed",
            "note": f"Must reject stale support after the {case_type} mutation.",
        },
    )
    assert reviewed_again.status_code == 409, reviewed_again.text
    assert reviewed_again.json()["detail"] == "Case decision requires exact-current provenance support"

    with SessionLocal() as db:
        decisions = list(db.scalars(select(ReviewDecision).where(ReviewDecision.case_id == case_id)))
        judgments = list(db.scalars(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)))
        assert len(decisions) == 1
        assert len(judgments) == 1
        assert judgments[0].review_decision_id == decisions[0].id
        assert decisions[0].decision == "confirmed"


@pytest.mark.parametrize("case_type", P1_RULES)
def test_conflicting_real_judgments_serialize_into_deterministic_history(client, auth, monkeypatch, case_type):
    """Each P1 rule serializes two incompatible production decisions deterministically."""
    _prepare_p1_case(
        client,
        auth,
        case_type=case_type,
        suffix=f"PG-CONFLICTING-{case_type.upper()}",
    )
    case_id, finding_id, initial_status = _current_case_and_finding(case_type)

    first_judgment_flushed = threading.Event()
    allow_first_commit = threading.Event()
    second_started = threading.Event()
    second_finished = threading.Event()
    worker_errors: list[BaseException] = []
    outcomes: dict[str, int] = {}

    original_record = legacy_cases_api.record_judgment_provenance

    def record_then_pause_first(*args, **kwargs):
        judgment = original_record(*args, **kwargs)
        assert judgment is not None
        review_decision = kwargs["review_decision"]
        if review_decision.decision == "confirmed":
            first_judgment_flushed.set()
            assert allow_first_commit.wait(timeout=3.0)
        return judgment

    monkeypatch.setattr(legacy_cases_api, "record_judgment_provenance", record_then_pause_first)

    def decide(name: str, decision: str, note: str) -> None:
        try:
            if name == "second":
                second_started.set()
            response = client.post(
                f"/api/cases/{case_id}/decision",
                headers=auth,
                json={"decision": decision, "note": note},
            )
            outcomes[name] = response.status_code
            assert response.status_code == 200, response.text
        except BaseException as exc:
            worker_errors.append(exc)
        finally:
            if name == "second":
                second_finished.set()

    first = threading.Thread(
        target=decide,
        args=("first", "confirmed", f"First conflicting PostgreSQL judgment for {case_type}."),
        daemon=True,
    )
    first.start()
    assert first_judgment_flushed.wait(timeout=2.0)

    second = threading.Thread(
        target=decide,
        args=("second", "dismissed", f"Second conflicting PostgreSQL judgment for {case_type}."),
        daemon=True,
    )
    second.start()
    assert second_started.wait(timeout=1.0)
    time.sleep(0.35)
    assert not second_finished.is_set(), f"the second {case_type} judgment must block behind the first transaction"

    allow_first_commit.set()
    first.join(timeout=3.0)
    second.join(timeout=3.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert not worker_errors
    assert outcomes == {"first": 200, "second": 200}

    with SessionLocal() as db:
        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == "dismissed"

        decisions = list(db.scalars(select(ReviewDecision).where(ReviewDecision.case_id == case_id)))
        judgments = list(db.scalars(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)))
        assert len(decisions) == 2
        assert len(judgments) == 2
        assert {decision.decision for decision in decisions} == {"confirmed", "dismissed"}
        assert {judgment.review_decision_id for judgment in judgments} == {decision.id for decision in decisions}

        by_decision = {judgment.decision: judgment for judgment in judgments}
        assert by_decision["confirmed"].previous_state == initial_status
        assert by_decision["dismissed"].previous_state == "confirmed"
