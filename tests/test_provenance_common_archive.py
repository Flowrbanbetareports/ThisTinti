from __future__ import annotations

import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, OperationChain
from app.provenance_models import ProvenanceFinding
from app.services.finding_provenance import (
    currency_mismatch_finding_matches_current_support,
    duplicate_number_finding_matches_current_support,
)
from app.services.rules import analyze_chain


def _payload(*, document_type: str, number: str, currency: str, order_number: str | None = None) -> bytes:
    data: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-30",
        "supplier_name": "Common Archive Provenance Supplier",
        "supplier_vat": "IT00000000141",
        "currency": currency,
        "lines": [
            {
                "line_no": 1,
                "sku": f"ARCH-{number}",
                "description": "Common archive provenance regression",
                "quantity": 1,
                "unit_price": 10,
                "discount_rate": 0,
                "tax_rate": 22,
                "line_total": 10,
            }
        ],
    }
    if order_number is not None:
        data["references"] = {"order_numbers": [order_number]}
    return json.dumps(data).encode("utf-8")


def _upload(client, auth, *, document_type: str, number: str, currency: str, order_number: str | None = None):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"{number}-{document_type}.json",
                _payload(
                    document_type=document_type,
                    number=number,
                    currency=currency,
                    order_number=order_number,
                ),
                "application/json",
            )
        },
    )


def _latest_finding(db, case: DiscrepancyCase) -> ProvenanceFinding:
    finding = db.scalar(
        select(ProvenanceFinding)
        .where(
            ProvenanceFinding.tenant_id == case.tenant_id,
            ProvenanceFinding.case_id == case.id,
        )
        .order_by(ProvenanceFinding.version.desc())
    )
    assert finding is not None
    return finding


def _finding_count(db, case: DiscrepancyCase) -> int:
    return len(
        list(
            db.scalars(
                select(ProvenanceFinding).where(
                    ProvenanceFinding.tenant_id == case.tenant_id,
                    ProvenanceFinding.case_id == case.id,
                )
            )
        )
    )


def test_duplicate_number_support_fails_closed_when_document_is_archived(client, auth):
    order_number = "PO-DUP-ARCH-141"
    order = _upload(client, auth, document_type="order", number=order_number, currency="EUR")
    first = _upload(
        client,
        auth,
        document_type="invoice",
        number="DUP-ARCH-141",
        currency="EUR",
        order_number=order_number,
    )
    second = _upload(
        client,
        auth,
        document_type="invoice",
        number="DUP-ARCH-141",
        currency="EUR",
        order_number=order_number,
    )
    assert order.status_code == 201, order.text
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    archived_id = second.json()["document"]["id"]

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "duplicate_document_number"))
        assert case is not None
        finding = _latest_finding(db, case)
        chain = db.get(OperationChain, case.chain_id)
        document = db.get(Document, archived_id)
        assert chain is not None
        assert document is not None and document.archived is False
        assert duplicate_number_finding_matches_current_support(db, finding=finding) is True
        count_before = _finding_count(db, case)

        document.archived = True
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        assert duplicate_number_finding_matches_current_support(db, finding=finding) is False
        assert _finding_count(db, case) == count_before

        document.archived = False
        db.flush()
        analyze_chain(db, chain)
        db.flush()
        assert duplicate_number_finding_matches_current_support(db, finding=finding) is True
        assert _finding_count(db, case) == count_before


def test_currency_mismatch_support_fails_closed_when_document_is_archived(client, auth):
    order = _upload(client, auth, document_type="order", number="PO-CUR-ARCH-141", currency="EUR")
    invoice = _upload(
        client,
        auth,
        document_type="invoice",
        number="INV-CUR-ARCH-141",
        currency="USD",
        order_number="PO-CUR-ARCH-141",
    )
    assert order.status_code == 201, order.text
    assert invoice.status_code == 201, invoice.text
    archived_id = invoice.json()["document"]["id"]

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "currency_mismatch"))
        assert case is not None
        finding = _latest_finding(db, case)
        chain = db.get(OperationChain, case.chain_id)
        document = db.get(Document, archived_id)
        assert chain is not None
        assert document is not None and document.archived is False
        assert currency_mismatch_finding_matches_current_support(db, finding=finding) is True
        count_before = _finding_count(db, case)

        document.archived = True
        db.flush()
        analyze_chain(db, chain)
        db.flush()

        assert currency_mismatch_finding_matches_current_support(db, finding=finding) is False
        assert _finding_count(db, case) == count_before

        document.archived = False
        db.flush()
        analyze_chain(db, chain)
        db.flush()
        assert currency_mismatch_finding_matches_current_support(db, finding=finding) is True
        assert _finding_count(db, case) == count_before
