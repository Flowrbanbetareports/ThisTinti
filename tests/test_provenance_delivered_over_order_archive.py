from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, OperationChain, ReviewDecision
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment
from app.services.delivered_over_order_provenance import (
    delivered_over_order_finding_matches_current_support,
)
from app.services.rules import analyze_chain


def _payload(*, document_type: str, number: str, quantity: str, order_number: str | None = None) -> bytes:
    line: dict[str, object] = {
        "line_no": 1,
        "sku": "DEL-ARCHIVE-SKU",
        "description": "Delivered over order archive qualification regression",
        "quantity": quantity,
        "unit_of_measure": "EA",
        "discount_rate": "0",
        "tax_rate": "0",
    }
    if document_type != "delivery":
        line.update({"unit_price": "5.00", "price_base_quantity": "1", "line_total": "50.00"})

    data: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-30",
        "supplier_name": "Delivered Archive Supplier",
        "supplier_vat": "IT00000000079",
        "currency": "EUR",
        "lines": [line],
    }
    if order_number is not None:
        data["references"] = {"order_numbers": [order_number]}
    return json.dumps(data).encode("utf-8")


def _upload(client, auth, *, document_type: str, number: str, quantity: str, order_number: str | None = None):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"{number}.json",
                _payload(
                    document_type=document_type,
                    number=number,
                    quantity=quantity,
                    order_number=order_number,
                ),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["document"]["id"]


@pytest.mark.parametrize("archived_role", ["order", "delivery"])
def test_delivered_over_order_archive_invalidates_current_support_and_blocks_judgment(client, auth, archived_role):
    order_number = f"PO-DEL-ARCHIVE-{archived_role}"
    order_id = _upload(
        client,
        auth,
        document_type="order",
        number=order_number,
        quantity="10",
    )
    delivery_id = _upload(
        client,
        auth,
        document_type="delivery",
        number=f"DDT-DEL-ARCHIVE-{archived_role}",
        quantity="12",
        order_number=order_number,
    )
    target_id = order_id if archived_role == "order" else delivery_id

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "delivered_over_order"))
        assert case is not None
        finding = db.scalar(
            select(ProvenanceFinding)
            .where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
            .order_by(ProvenanceFinding.version.desc())
        )
        assert finding is not None
        assert delivered_over_order_finding_matches_current_support(db, finding=finding) is True
        chain = db.get(OperationChain, case.chain_id)
        target = db.get(Document, target_id)
        assert chain is not None
        assert target is not None and target.archived is False

        finding_count_before = len(
            list(
                db.scalars(
                    select(ProvenanceFinding).where(
                        ProvenanceFinding.tenant_id == case.tenant_id,
                        ProvenanceFinding.case_id == case.id,
                    )
                )
            )
        )
        case_id = case.id
        finding_id = finding.id

        target.archived = True
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        assert delivered_over_order_finding_matches_current_support(db, finding=finding) is False
        assert (
            len(
                list(
                    db.scalars(
                        select(ProvenanceFinding).where(
                            ProvenanceFinding.tenant_id == case.tenant_id,
                            ProvenanceFinding.case_id == case.id,
                        )
                    )
                )
            )
            == finding_count_before
        )
        assert case.status == "superseded"
        db.commit()

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Archived evidence must not support a new provenance judgment."},
    )
    assert reviewed.status_code == 409, reviewed.text

    with SessionLocal() as db:
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert judgment is None
        assert db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id)) is None

        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == "superseded"
        chain = db.get(OperationChain, case.chain_id)
        finding = db.get(ProvenanceFinding, finding_id)
        target = db.get(Document, target_id)
        assert chain is not None and finding is not None and target is not None

        target.archived = False
        db.flush()
        analyze_chain(db, chain)
        db.flush()
        assert delivered_over_order_finding_matches_current_support(db, finding=finding) is True
        assert case.status == "open"
