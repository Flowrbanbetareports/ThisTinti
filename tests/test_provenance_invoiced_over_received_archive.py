from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, OperationChain
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment
from app.services.invoiced_over_received_provenance import (
    invoiced_over_received_finding_matches_current_support,
)
from app.services.rules import analyze_chain


def _payload(
    *,
    document_type: str,
    number: str,
    quantity: str,
    order_number: str | None = None,
) -> bytes:
    line: dict[str, object] = {
        "line_no": 1,
        "sku": "INV-ARCHIVE-SKU",
        "description": "Invoiced over received archive qualification regression",
        "quantity": quantity,
        "unit_of_measure": "EA",
        "discount_rate": "0",
        "tax_rate": "0",
    }
    if document_type != "delivery":
        line.update({"unit_price": "5.00", "price_base_quantity": "1", "line_total": str(Decimal(quantity) * 5)})

    data: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-30",
        "supplier_name": "Invoice Archive Supplier",
        "supplier_vat": "IT00000000081",
        "currency": "EUR",
        "lines": [line],
    }
    if order_number is not None:
        data["references"] = {"order_numbers": [order_number]}
    return json.dumps(data).encode("utf-8")


def _upload(
    client,
    auth,
    *,
    document_type: str,
    number: str,
    quantity: str,
    order_number: str | None = None,
) -> str:
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


@pytest.mark.parametrize("archived_role", ["delivery", "invoice", "order_fallback"])
def test_invoiced_over_received_archive_invalidates_current_support_and_blocks_judgment(client, auth, archived_role):
    order_number = f"PO-INV-ARCHIVE-{archived_role}"
    order_id = _upload(
        client,
        auth,
        document_type="order",
        number=order_number,
        quantity="10",
    )
    delivery_id = None
    if archived_role != "order_fallback":
        delivery_id = _upload(
            client,
            auth,
            document_type="delivery",
            number=f"DDT-INV-ARCHIVE-{archived_role}",
            quantity="10",
            order_number=order_number,
        )
    invoice_id = _upload(
        client,
        auth,
        document_type="invoice",
        number=f"INV-ARCHIVE-{archived_role}",
        quantity="12",
        order_number=order_number,
    )

    if archived_role == "delivery":
        assert delivery_id is not None
        target_id = delivery_id
    elif archived_role == "invoice":
        target_id = invoice_id
    else:
        target_id = order_id

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "invoiced_over_received"))
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
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is True
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

        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is False
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
        db.commit()

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Archived evidence must not support a new provenance judgment."},
    )
    assert reviewed.status_code == 200, reviewed.text

    with SessionLocal() as db:
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert judgment is None

        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        chain = db.get(OperationChain, case.chain_id)
        finding = db.get(ProvenanceFinding, finding_id)
        target = db.get(Document, target_id)
        assert chain is not None and finding is not None and target is not None

        target.archived = False
        db.flush()
        analyze_chain(db, chain)
        db.flush()
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is True
