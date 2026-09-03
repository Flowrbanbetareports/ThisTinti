import json

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import DiscrepancyCase, OperationChain, RuleProposal
from app.services.rules import analyze_chain


def _upload(client, auth, filename, payload):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )
    assert response.status_code == 201, response.text


def _line(quantity):
    return {
        "sku": "P1-ISO-1",
        "description": "Qualified P1 isolation fixture",
        "quantity": quantity,
        "unit_price": 10,
        "line_total": quantity * 10,
        "unit_of_measure": "EA",
        "price_base_quantity": 1,
    }


def test_frozen_p1_quantity_findings_ignore_unrelated_discovery_state(client, auth):
    _upload(
        client,
        auth,
        "p1-isolation-order.json",
        {
            "document_type": "order",
            "number": "PO-P1-ISO-1",
            "currency": "EUR",
            "lines": [_line(1)],
        },
    )
    _upload(
        client,
        auth,
        "p1-isolation-delivery.json",
        {
            "document_type": "delivery",
            "number": "DDT-P1-ISO-1",
            "currency": "EUR",
            "references": {"order_numbers": ["PO-P1-ISO-1"]},
            "lines": [_line(2)],
        },
    )
    _upload(
        client,
        auth,
        "p1-isolation-invoice.json",
        {
            "document_type": "invoice",
            "number": "INV-P1-ISO-1",
            "currency": "EUR",
            "references": {"order_numbers": ["PO-P1-ISO-1"]},
            "lines": [_line(3)],
        },
    )

    with SessionLocal() as db:
        chain = db.scalar(select(OperationChain))
        assert chain is not None
        tenant_id = chain.tenant_id

        before = {
            case.case_type: case.status
            for case in db.scalars(
                select(DiscrepancyCase).where(
                    DiscrepancyCase.tenant_id == tenant_id,
                    DiscrepancyCase.chain_id == chain.id,
                    DiscrepancyCase.case_type.in_({"delivered_over_order", "invoiced_over_received"}),
                )
            )
        }
        assert before.get("delivered_over_order") in {"open", "needs_review"}
        assert before.get("invoiced_over_received") in {"open", "needs_review"}

        db.execute(delete(RuleProposal).where(RuleProposal.tenant_id == tenant_id))
        db.add(
            RuleProposal(
                tenant_id=tenant_id,
                rule_code="return_without_credit",
                title="Unrelated Discovery proposal",
                description="Must not control the frozen Qualified P1 rule pack.",
                rationale="Adversarial isolation fixture.",
                confidence=0.5,
                status="needs_confirmation",
            )
        )
        db.flush()

        output = analyze_chain(db, chain)
        db.commit()

        active = {case.case_type for case in output if case.status in {"open", "needs_review"}}
        assert "delivered_over_order" in active
        assert "invoiced_over_received" in active

        persisted = {
            case.case_type: case.status
            for case in db.scalars(
                select(DiscrepancyCase).where(
                    DiscrepancyCase.tenant_id == tenant_id,
                    DiscrepancyCase.chain_id == chain.id,
                    DiscrepancyCase.case_type.in_({"delivered_over_order", "invoiced_over_received"}),
                )
            )
        }
        assert persisted["delivered_over_order"] != "superseded"
        assert persisted["invoiced_over_received"] != "superseded"
