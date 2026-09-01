from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, DocumentLine, ReviewDecision
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment
from tests.test_provenance_delivered_over_order import _upload_overdelivery
from tests.test_provenance_invoiced_over_received import _upload_overinvoice
from tests.test_provenance_payment_over_invoice import _upload_overpayment


pytestmark = pytest.mark.skipif(
    not os.getenv("THISTINTI_TEST_POSTGRES_URL"),
    reason="requires a real PostgreSQL database via THISTINTI_TEST_POSTGRES_URL",
)


def _current_case_and_finding(case_type: str):
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


def _assert_stale_finding_rejected(client, auth, *, case_id: str, finding_id: str, original_status: str, note: str):
    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": note},
    )
    assert reviewed.status_code == 409, reviewed.text
    assert reviewed.json()["detail"] == "Case decision requires exact-current provenance support"

    with SessionLocal() as db:
        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == original_status
        assert db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id)) is None
        assert db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)) is None


def test_committed_quantity_mutation_invalidates_finding_before_real_judgment(client, auth):
    """Mutation-first support drift must fail closed through the real review endpoint.

    The finding is created from an over-delivery (12 > 10). A separate committed
    transaction then changes the delivery quantity to 8 before review begins, so the
    prior finding no longer matches current semantic support. The production review
    path must refuse to bind a human judgment to that stale finding and roll back the
    transient ReviewDecision.
    """
    _order_id, delivery_id = _upload_overdelivery(
        client,
        auth,
        suffix="PG-MUTATION-FIRST",
        ordered="10",
        delivered="12",
    )
    case_id, finding_id, original_status = _current_case_and_finding("delivered_over_order")

    # A distinct transaction commits a semantically material support mutation before
    # the judgment transaction acquires its support locks.
    with SessionLocal() as mutator, mutator.begin():
        delivery_line = mutator.scalar(
            select(DocumentLine).where(
                DocumentLine.document_id == delivery_id,
                DocumentLine.line_no == 1,
            )
        )
        assert delivery_line is not None
        assert Decimal(delivery_line.quantity) == Decimal("12")
        delivery_line.quantity = Decimal("8")

    _assert_stale_finding_rejected(
        client,
        auth,
        case_id=case_id,
        finding_id=finding_id,
        original_status=original_status,
        note="Must not bind a stale over-delivery finding after support mutation.",
    )

    with SessionLocal() as db:
        persisted_quantity = db.scalar(
            select(DocumentLine.quantity).where(
                DocumentLine.document_id == delivery_id,
                DocumentLine.line_no == 1,
            )
        )
        assert Decimal(persisted_quantity) == Decimal("8")


def test_committed_invoice_quantity_mutation_invalidates_finding_before_real_judgment(client, auth):
    """An invoiced-over-received finding must not survive a committed invoice correction."""
    suffix = "PG-MUTATION-FIRST"
    _upload_overinvoice(
        client,
        auth,
        suffix=suffix,
        received="10",
        invoiced="12",
    )
    case_id, finding_id, original_status = _current_case_and_finding("invoiced_over_received")
    invoice_number = f"INV-PROV-{suffix}"

    with SessionLocal() as mutator, mutator.begin():
        invoice_line = mutator.scalar(
            select(DocumentLine)
            .join(Document, Document.id == DocumentLine.document_id)
            .where(
                Document.number == invoice_number,
                DocumentLine.line_no == 1,
            )
        )
        assert invoice_line is not None
        assert Decimal(invoice_line.quantity) == Decimal("12")
        invoice_line.quantity = Decimal("8")

    _assert_stale_finding_rejected(
        client,
        auth,
        case_id=case_id,
        finding_id=finding_id,
        original_status=original_status,
        note="Must not bind a stale invoiced-over-received finding after invoice correction.",
    )

    with SessionLocal() as db:
        persisted_quantity = db.scalar(
            select(DocumentLine.quantity)
            .join(Document, Document.id == DocumentLine.document_id)
            .where(
                Document.number == invoice_number,
                DocumentLine.line_no == 1,
            )
        )
        assert Decimal(persisted_quantity) == Decimal("8")


def test_committed_payment_total_mutation_invalidates_finding_before_real_judgment(client, auth):
    """A payment-over-invoice finding must fail closed after its direct total changes."""
    suffix = "PG-MUTATION-FIRST"
    _upload_overpayment(
        client,
        auth,
        suffix=suffix,
        invoice_total="100.00",
        payment_total="125.00",
    )
    case_id, finding_id, original_status = _current_case_and_finding("payment_over_invoice")
    payment_number = f"PAY-PROV-{suffix}"

    with SessionLocal() as mutator, mutator.begin():
        payment_line = mutator.scalar(
            select(DocumentLine)
            .join(Document, Document.id == DocumentLine.document_id)
            .where(
                Document.number == payment_number,
                DocumentLine.line_no == 1,
            )
        )
        assert payment_line is not None
        assert Decimal(payment_line.line_total) == Decimal("125.00")
        payment_line.line_total = Decimal("90.00")

    _assert_stale_finding_rejected(
        client,
        auth,
        case_id=case_id,
        finding_id=finding_id,
        original_status=original_status,
        note="Must not bind a stale payment-over-invoice finding after payment-total correction.",
    )

    with SessionLocal() as db:
        persisted_total = db.scalar(
            select(DocumentLine.line_total)
            .join(Document, Document.id == DocumentLine.document_id)
            .where(
                Document.number == payment_number,
                DocumentLine.line_no == 1,
            )
        )
        assert Decimal(persisted_total) == Decimal("90.00")
