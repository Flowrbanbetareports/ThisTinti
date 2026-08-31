from __future__ import annotations

import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, OperationChain
from app.provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact
from app.services.payment_without_invoice_provenance import (
    payment_without_invoice_finding_matches_current_support,
)
from app.services.rules import analyze_chain


def _payload() -> bytes:
    return json.dumps(
        {
            "document_type": "payment",
            "number": "PAY-ARCHIVE-STATE",
            "document_date": "2026-08-29",
            "supplier_name": "Archive State Supplier",
            "supplier_vat": "IT00000000078",
            "currency": "EUR",
            "lines": [
                {
                    "line_no": 1,
                    "sku": "ARCHIVE-STATE-SKU",
                    "description": "Archive state qualification regression",
                    "quantity": "1",
                    "unit_of_measure": "EA",
                    "unit_price": "50.00",
                    "price_base_quantity": "1",
                    "discount_rate": "0",
                    "tax_rate": "0",
                    "line_total": "50.00",
                }
            ],
        }
    ).encode("utf-8")


def _linked_payload(*, document_type: str, number: str, invoice_number: str | None = None) -> bytes:
    payload: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-29",
        "supplier_name": "Archived Invoice Transition Supplier",
        "supplier_vat": "IT00000000079",
        "currency": "EUR",
        "lines": [
            {
                "line_no": 1,
                "sku": "ARCHIVED-INVOICE-SKU",
                "description": "Archived invoice transition qualification regression",
                "quantity": "1",
                "unit_of_measure": "EA",
                "unit_price": "60.00",
                "price_base_quantity": "1",
                "discount_rate": "0",
                "tax_rate": "0",
                "line_total": "60.00",
            }
        ],
    }
    if invoice_number is not None:
        payload["references"] = {"invoice_numbers": [invoice_number]}
    return json.dumps(payload).encode("utf-8")


def test_payment_without_invoice_fails_closed_when_supporting_payment_is_archived(client, auth):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("payment-archive-state.json", _payload(), "application/json")},
    )
    assert response.status_code == 201, response.text

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "payment_without_invoice"))
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
        chain = db.get(OperationChain, case.chain_id)
        assert chain is not None and chain.payment_document_id is not None
        payment = db.get(Document, chain.payment_document_id)
        assert payment is not None and payment.archived is False
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True

        fact_count_before = len(
            list(
                db.scalars(
                    select(ProvenanceFact).where(
                        ProvenanceFact.tenant_id == case.tenant_id,
                        ProvenanceFact.fact_key == f"operation_chain:{chain.id}:payment_without_invoice_snapshot",
                    )
                )
            )
        )
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

        payment.archived = True
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        assert (
            len(
                list(
                    db.scalars(
                        select(ProvenanceFact).where(
                            ProvenanceFact.tenant_id == case.tenant_id,
                            ProvenanceFact.fact_key == f"operation_chain:{chain.id}:payment_without_invoice_snapshot",
                        )
                    )
                )
            )
            == fact_count_before
        )
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

        payment.archived = False
        db.flush()
        analyze_chain(db, chain)
        db.flush()
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True


def test_archived_linked_invoice_restores_exact_current_payment_without_invoice(client, auth):
    invoice_number = "INV-ARCHIVED-TRANSITION"
    invoice_response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                "invoice-archived-transition.json",
                _linked_payload(document_type="invoice", number=invoice_number),
                "application/json",
            )
        },
    )
    assert invoice_response.status_code == 201, invoice_response.text
    payment_response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                "payment-archived-transition.json",
                _linked_payload(
                    document_type="payment",
                    number="PAY-ARCHIVED-TRANSITION",
                    invoice_number=invoice_number,
                ),
                "application/json",
            )
        },
    )
    assert payment_response.status_code == 201, payment_response.text

    with SessionLocal() as db:
        invoice = db.scalar(select(Document).where(Document.number == invoice_number))
        payment = db.scalar(select(Document).where(Document.number == "PAY-ARCHIVED-TRANSITION"))
        assert invoice is not None and payment is not None
        chain = db.scalar(
            select(OperationChain).where(
                OperationChain.tenant_id == invoice.tenant_id,
                OperationChain.invoice_document_id == invoice.id,
            )
        )
        assert chain is not None
        assert chain.payment_document_id == payment.id
        assert (
            db.scalar(
                select(DiscrepancyCase).where(
                    DiscrepancyCase.tenant_id == chain.tenant_id,
                    DiscrepancyCase.chain_id == chain.id,
                    DiscrepancyCase.case_type == "payment_without_invoice",
                )
            )
            is None
        )

        invoice.archived = True
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        case = db.scalar(
            select(DiscrepancyCase).where(
                DiscrepancyCase.tenant_id == chain.tenant_id,
                DiscrepancyCase.chain_id == chain.id,
                DiscrepancyCase.case_type == "payment_without_invoice",
            )
        )
        assert case is not None
        assert case.status == "open"
        finding = db.scalar(
            select(ProvenanceFinding)
            .where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
            .order_by(ProvenanceFinding.version.desc())
        )
        assert finding is not None
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True

        fact_id = db.scalar(
            select(ProvenanceFindingFact.fact_id).where(
                ProvenanceFindingFact.tenant_id == finding.tenant_id,
                ProvenanceFindingFact.finding_id == finding.id,
            )
        )
        assert fact_id is not None
        fact = db.get(ProvenanceFact, fact_id)
        assert fact is not None
        snapshot = json.loads(fact.value_json)
        assert snapshot["invoice_document_ids"] == [invoice.id]
        assert snapshot["active_invoice_document_ids"] == []
        assert snapshot["active_payment_document_ids"] == [payment.id]
        assert snapshot["predicate"] == {"invoice_role_empty": True, "payments_present": True}

        invoice.archived = False
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        assert case.status == "superseded"
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
