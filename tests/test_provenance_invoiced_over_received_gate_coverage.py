from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase
from app.provenance_models import ProvenanceFinding
from app.services.invoiced_over_received_provenance import (
    invoiced_over_received_finding_matches_current_support,
)


def _upload(client, auth, *, kind: str, number: str, quantity: str, price: str | None, order_number: str | None = None):
    line: dict[str, object] = {
        "line_no": 1,
        "sku": "INV-GATE-ITEM",
        "description": "Gate coverage item",
        "quantity": quantity,
        "unit_of_measure": "EA",
        "discount_rate": 0,
        "tax_rate": 22,
    }
    if price is not None:
        line["unit_price"] = price
        line["price_base_quantity"] = "1"
        line["line_total"] = str(Decimal(quantity) * Decimal(price))
    payload: dict[str, object] = {
        "document_type": kind,
        "number": number,
        "document_date": "2026-08-29",
        "supplier_name": "Gate Coverage Supplier",
        "supplier_vat": "IT00000000043",
        "currency": "EUR",
        "lines": [line],
    }
    if order_number is not None:
        payload["references"] = {"order_numbers": [order_number]}
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (f"{number}.json", json.dumps(payload).encode(), "application/json")},
    )
    assert response.status_code == 201, response.text


def _current_case_and_finding(db):
    case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "invoiced_over_received"))
    assert case is not None
    finding = db.scalar(
        select(ProvenanceFinding).where(ProvenanceFinding.case_id == case.id).order_by(ProvenanceFinding.version.desc())
    )
    assert finding is not None
    return case, finding


def test_invoiced_over_received_qualifies_commercial_fallback_without_delivery(client, auth):
    order_number = "PO-INV-GATE-FALLBACK"
    _upload(client, auth, kind="order", number=order_number, quantity="10", price="5")
    _upload(
        client,
        auth,
        kind="invoice",
        number="INV-GATE-FALLBACK",
        quantity="12",
        price="5",
        order_number=order_number,
    )

    with SessionLocal() as db:
        case, finding = _current_case_and_finding(db)
        assert Decimal(case.amount_estimate) == Decimal("10.00")
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is True


def test_invoiced_over_received_rejects_tampered_amount_and_rule_configuration(client, auth):
    order_number = "PO-INV-GATE-STALE"
    _upload(client, auth, kind="order", number=order_number, quantity="10", price="5")
    _upload(
        client, auth, kind="delivery", number="DDT-INV-GATE-STALE", quantity="10", price=None, order_number=order_number
    )
    _upload(
        client,
        auth,
        kind="invoice",
        number="INV-GATE-STALE",
        quantity="12",
        price="5",
        order_number=order_number,
    )

    with SessionLocal() as db:
        case, finding = _current_case_and_finding(db)
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is True

        original_amount = case.amount_estimate
        case.amount_estimate = Decimal("999.99")
        db.flush()
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is False

        case.amount_estimate = original_amount
        finding.rule_configuration_hash = "0" * 64
        db.flush()
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is False
