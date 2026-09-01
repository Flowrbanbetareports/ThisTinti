from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, DocumentLine, ReviewDecision
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment
from tests.test_provenance_delivered_over_order import _upload_overdelivery


pytestmark = pytest.mark.skipif(
    not os.getenv("THISTINTI_TEST_POSTGRES_URL"),
    reason="requires a real PostgreSQL database via THISTINTI_TEST_POSTGRES_URL",
)


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

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "delivered_over_order"))
        assert case is not None
        finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert finding is not None
        case_id = case.id
        finding_id = finding.id
        original_status = case.status

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

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={
            "decision": "confirmed",
            "note": "Must not bind a stale over-delivery finding after support mutation.",
        },
    )
    assert reviewed.status_code == 409, reviewed.text
    assert reviewed.json()["detail"] == "Case decision requires exact-current provenance support"

    with SessionLocal() as db:
        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == original_status
        assert db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id)) is None
        assert (
            db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)) is None
        )
        persisted_quantity = db.scalar(
            select(DocumentLine.quantity).where(
                DocumentLine.document_id == delivery_id,
                DocumentLine.line_no == 1,
            )
        )
        assert Decimal(persisted_quantity) == Decimal("8")
