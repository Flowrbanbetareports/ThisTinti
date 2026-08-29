from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, OperationChain
from app.provenance_models import ProvenanceFact, ProvenanceFinding
from app.services.payment_without_invoice_provenance import (
    payment_without_invoice_finding_matches_current_support,
)
from app.services.rules import analyze_chain


def _payload() -> bytes:
    return json.dumps(
        {
            "document_type": "payment",
            "number": "PAY-PARSE-STATUS",
            "document_date": "2026-08-29",
            "supplier_name": "Parser State Supplier",
            "supplier_vat": "IT00000000077",
            "currency": "EUR",
            "lines": [
                {
                    "line_no": 1,
                    "sku": "PARSE-STATE-SKU",
                    "description": "Parser state qualification regression",
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


@pytest.mark.parametrize("unsupported_status", ["pending", "failed", "error", "degraded"])
def test_payment_without_invoice_fails_closed_for_unsupported_payment_parse_status(
    client,
    auth,
    unsupported_status,
):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("payment-parse-status.json", _payload(), "application/json")},
    )
    assert response.status_code == 201, response.text

    with SessionLocal() as db:
        case = db.scalar(
            select(DiscrepancyCase).where(DiscrepancyCase.case_type == "payment_without_invoice")
        )
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
        assert payment is not None
        assert payment.parse_status == "parsed"
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True

        fact_count_before = len(
            list(
                db.scalars(
                    select(ProvenanceFact).where(
                        ProvenanceFact.tenant_id == case.tenant_id,
                        ProvenanceFact.fact_key
                        == f"operation_chain:{chain.id}:payment_without_invoice_snapshot",
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

        payment.parse_status = unsupported_status
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        assert len(
            list(
                db.scalars(
                    select(ProvenanceFact).where(
                        ProvenanceFact.tenant_id == case.tenant_id,
                        ProvenanceFact.fact_key
                        == f"operation_chain:{chain.id}:payment_without_invoice_snapshot",
                    )
                )
            )
        ) == fact_count_before
        assert len(
            list(
                db.scalars(
                    select(ProvenanceFinding).where(
                        ProvenanceFinding.tenant_id == case.tenant_id,
                        ProvenanceFinding.case_id == case.id,
                    )
                )
            )
        ) == finding_count_before

        payment.parse_status = "parsed"
        db.flush()
        analyze_chain(db, chain)
        db.flush()
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True
