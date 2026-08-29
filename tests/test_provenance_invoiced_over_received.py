from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, OperationChain
from app.provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceJudgment, ProvenanceOrigin
from app.services.invoiced_over_received_provenance import invoiced_over_received_finding_matches_current_support
from app.services.rules import analyze_chain


def _payload(*, document_type: str, number: str, quantity: str, uom: str | None, order_number: str | None = None, unit_price: str | None = None, price_base_quantity: str | None = None) -> bytes:
    line: dict[str, object] = {
        "line_no": 1,
        "sku": "INV-PROV-ITEM",
        "description": "Invoiced over received provenance item",
        "quantity": quantity,
        "discount_rate": 0,
        "tax_rate": 22,
    }
    if uom is not None:
        line["unit_of_measure"] = uom
    if unit_price is not None:
        line["unit_price"] = unit_price
    if price_base_quantity is not None:
        line["price_base_quantity"] = price_base_quantity
    if document_type not in {"delivery", "return"}:
        assert unit_price is not None
        base = Decimal(price_base_quantity or "1")
        line["line_total"] = str(Decimal(quantity) * Decimal(unit_price) / base)
    data: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-29",
        "supplier_name": "Invoice Provenance Supplier",
        "supplier_vat": "IT00000000042",
        "currency": "EUR",
        "lines": [line],
    }
    if order_number is not None:
        data["references"] = {"order_numbers": [order_number]}
    return json.dumps(data).encode("utf-8")


def _upload(client, auth, *, document_type: str, number: str, quantity: str, uom: str | None, order_number: str | None = None, unit_price: str | None = None, price_base_quantity: str | None = None):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (f"{number}.json", _payload(document_type=document_type, number=number, quantity=quantity, uom=uom, order_number=order_number, unit_price=unit_price, price_base_quantity=price_base_quantity), "application/json")},
    )


def _case(db) -> DiscrepancyCase | None:
    return db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "invoiced_over_received"))


def _findings(db, case: DiscrepancyCase) -> list[ProvenanceFinding]:
    return list(db.scalars(select(ProvenanceFinding).where(ProvenanceFinding.tenant_id == case.tenant_id, ProvenanceFinding.case_id == case.id).order_by(ProvenanceFinding.version)))


def _upload_overinvoice(client, auth, *, suffix: str, received: str = "10", invoiced: str = "12", invoice_uom: str | None = "EA", invoice_base: str | None = "1") -> None:
    order_number = f"PO-INV-PROV-{suffix}"
    order = _upload(client, auth, document_type="order", number=order_number, quantity="10", uom="EA", unit_price="5", price_base_quantity="1")
    delivery = _upload(client, auth, document_type="delivery", number=f"DDT-INV-PROV-{suffix}", quantity=received, uom="EA", order_number=order_number)
    invoice = _upload(client, auth, document_type="invoice", number=f"INV-PROV-{suffix}", quantity=invoiced, uom=invoice_uom, order_number=order_number, unit_price="5", price_base_quantity=invoice_base)
    assert order.status_code == 201, order.text
    assert delivery.status_code == 201, delivery.text
    assert invoice.status_code == 201, invoice.text


def test_invoiced_over_received_binds_exact_reference_invoice_inputs_and_judgment(client, auth):
    _upload_overinvoice(client, auth, suffix="E2E")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("10.00")
        findings = _findings(db, case)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.rule_id == "builtin:invoiced_over_received"
        assert finding.rule_version == "1"
        assert len(finding.rule_configuration_hash) == 64
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is True
        links = list(db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == finding.id)))
        assert len(links) == 6
        facts = [db.get(ProvenanceFact, link.fact_id) for link in links]
        assert all(fact is not None for fact in facts)
        assert {fact.fact_type for fact in facts if fact is not None} == {
            "document_line.quantity",
            "document_line.unit_of_measure",
            "document_line.unit_price",
            "document_line.price_base_quantity",
        }
        for fact in facts:
            assert fact is not None
            origin = db.get(ProvenanceOrigin, fact.origin_id)
            assert origin is not None
            assert origin.origin_type == "DOCUMENT_EVIDENCE"
            assert origin.source_availability == "available"
            assert origin.locator_status == "present"
            assert origin.locator_type == "JSON_POINTER"
            assert origin.engine_id == "native-json-parser"
            assert origin.engine_version == "1"
        case_id = case.id
        finding_id = finding.id

    reviewed = client.post(f"/api/cases/{case_id}/decision", headers=auth, json={"decision": "confirmed", "note": "Qualified received and invoiced quantities and invoice pricing checked."})
    assert reviewed.status_code == 200, reviewed.text
    with SessionLocal() as db:
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert judgment is not None
        assert judgment.decision == "confirmed"


def test_invoiced_over_received_fails_closed_when_invoice_price_base_is_defaulted(client, auth):
    _upload_overinvoice(client, auth, suffix="DEFAULT-BASE", invoice_base=None)
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert _findings(db, case) == []


def test_invoiced_over_received_fails_closed_when_invoice_uom_is_not_direct(client, auth):
    _upload_overinvoice(client, auth, suffix="NO-UOM", invoice_uom=None)
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert _findings(db, case) == []


def test_invoiced_over_received_reanalysis_is_idempotent_and_new_delivery_versions_support(client, auth):
    _upload_overinvoice(client, auth, suffix="VERSION", received="10", invoiced="12")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        first = _findings(db, case)
        assert [finding.version for finding in first] == [1]
        first_id = first[0].id
        chain = db.get(OperationChain, case.chain_id)
        assert chain is not None
        analyze_chain(db, chain)
        db.flush()
        assert [finding.version for finding in _findings(db, case)] == [1]

    second = _upload(client, auth, document_type="delivery", number="DDT-INV-PROV-VERSION-2", quantity="1", uom="EA", order_number="PO-INV-PROV-VERSION")
    assert second.status_code == 201, second.text
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        findings = _findings(db, case)
        assert [finding.version for finding in findings] == [1, 2]
        assert findings[1].supersedes_finding_id == first_id
        assert invoiced_over_received_finding_matches_current_support(db, finding=findings[0]) is False
        assert invoiced_over_received_finding_matches_current_support(db, finding=findings[1]) is True


def test_invoiced_over_received_rejects_unavailable_support_before_human_binding(client, auth):
    _upload_overinvoice(client, auth, suffix="UNAVAILABLE")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        finding = _findings(db, case)[0]
        linked_fact_id = db.scalar(select(ProvenanceFindingFact.fact_id).where(ProvenanceFindingFact.finding_id == finding.id))
        assert linked_fact_id is not None
        fact = db.get(ProvenanceFact, linked_fact_id)
        assert fact is not None
        origin = db.get(ProvenanceOrigin, fact.origin_id)
        assert origin is not None
        origin.source_availability = "external_unavailable"
        db.commit()
        assert invoiced_over_received_finding_matches_current_support(db, finding=finding) is False
        case_id = case.id
        finding_id = finding.id

    reviewed = client.post(f"/api/cases/{case_id}/decision", headers=auth, json={"decision": "confirmed", "note": "Must not bind unavailable provenance."})
    assert reviewed.status_code == 200, reviewed.text
    with SessionLocal() as db:
        assert db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)) is None
