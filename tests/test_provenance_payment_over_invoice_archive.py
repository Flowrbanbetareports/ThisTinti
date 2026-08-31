from __future__ import annotations

import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, OperationChain
from app.provenance_models import ProvenanceFinding
from app.services.payment_over_invoice_provenance import (
    payment_over_invoice_finding_matches_current_support,
)
from app.services.rules import analyze_chain


def _payload(
    *, document_type: str, number: str, total: str, invoice_number: str | None = None
) -> bytes:
    payload: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-31",
        "supplier_name": "Payment Archive Regression Supplier",
        "supplier_vat": "IT00000000055",
        "currency": "EUR",
        "lines": [
            {
                "line_no": 1,
                "sku": f"PAY-ARCHIVE-{number}",
                "description": "Payment over invoice archived support regression",
                "quantity": "1",
                "unit_of_measure": "EA",
                "unit_price": total,
                "price_base_quantity": "1",
                "discount_rate": "0",
                "tax_rate": "0",
                "line_total": total,
            }
        ],
    }
    if invoice_number is not None:
        payload["references"] = {"invoice_numbers": [invoice_number]}
    return json.dumps(payload).encode("utf-8")


def _upload(
    client,
    auth,
    *,
    document_type: str,
    number: str,
    total: str,
    invoice_number: str | None = None,
) -> None:
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"{number}.json",
                _payload(
                    document_type=document_type,
                    number=number,
                    total=total,
                    invoice_number=invoice_number,
                ),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text


def test_payment_over_invoice_archived_support_fails_closed_and_cannot_mint_new_finding(
    client, auth
):
    invoice_number = "INV-PAY-ARCHIVE-V2"
    _upload(client, auth, document_type="invoice", number=invoice_number, total="100.00")
    _upload(
        client,
        auth,
        document_type="payment",
        number="PAY-ARCHIVE-V2",
        total="125.00",
        invoice_number=invoice_number,
    )

    with SessionLocal() as db:
        case = db.scalar(
            select(DiscrepancyCase).where(
                DiscrepancyCase.case_type == "payment_over_invoice"
            )
        )
        assert case is not None
        findings = list(
            db.scalars(
                select(ProvenanceFinding)
                .where(ProvenanceFinding.case_id == case.id)
                .order_by(ProvenanceFinding.version)
            )
        )
        assert len(findings) == 1
        finding = findings[0]
        chain = db.get(OperationChain, case.chain_id)
        assert chain is not None and chain.payment_document_id is not None
        payment = db.get(Document, chain.payment_document_id)
        assert payment is not None and payment.archived is False
        assert (
            payment_over_invoice_finding_matches_current_support(db, finding=finding)
            is True
        )

        payment.archived = True
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        assert (
            payment_over_invoice_finding_matches_current_support(db, finding=finding)
            is False
        )
        assert list(
            db.scalars(
                select(ProvenanceFinding)
                .where(ProvenanceFinding.case_id == case.id)
                .order_by(ProvenanceFinding.version)
            )
        ) == findings

        payment.archived = False
        db.flush()
        analyze_chain(db, chain)
        db.flush()
        assert (
            payment_over_invoice_finding_matches_current_support(db, finding=finding)
            is True
        )
