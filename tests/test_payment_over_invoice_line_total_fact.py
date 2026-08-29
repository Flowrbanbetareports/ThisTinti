from __future__ import annotations

import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document, DocumentLine
from app.provenance_models import ProvenanceFact, ProvenanceOrigin


def _upload_invoice(client, auth, *, number: str, explicit_line_total: bool):
    line: dict[str, object] = {
        "line_no": 1,
        "sku": f"PAY-TOTAL-{number}",
        "description": "Payment provenance line total",
        "quantity": "2",
        "unit_of_measure": "EA",
        "unit_price": "5",
        "price_base_quantity": "1",
        "discount_rate": "0",
        "tax_rate": "22",
    }
    if explicit_line_total:
        line["line_total"] = "10.00"
    payload = {
        "document_type": "invoice",
        "number": number,
        "document_date": "2026-08-29",
        "supplier_name": "Payment Provenance Supplier",
        "supplier_vat": "IT00000000043",
        "currency": "EUR",
        "lines": [line],
    }
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (f"{number}.json", json.dumps(payload).encode("utf-8"), "application/json")},
    )


def test_explicit_line_total_records_direct_document_evidence_fact(client, auth):
    response = _upload_invoice(client, auth, number="INV-PAY-TOTAL-DIRECT", explicit_line_total=True)
    assert response.status_code == 201, response.text

    with SessionLocal() as db:
        document = db.scalar(select(Document).where(Document.number == "INV-PAY-TOTAL-DIRECT"))
        assert document is not None
        line = db.scalar(select(DocumentLine).where(DocumentLine.document_id == document.id))
        assert line is not None
        fact = db.scalar(
            select(ProvenanceFact).where(
                ProvenanceFact.tenant_id == document.tenant_id,
                ProvenanceFact.fact_key == f"document_line:{line.id}:line_total",
            )
        )
        assert fact is not None
        assert fact.fact_type == "document_line.line_total"
        assert json.loads(fact.value_json) == "10.00"
        origin = db.get(ProvenanceOrigin, fact.origin_id)
        assert origin is not None
        assert origin.origin_type == "DOCUMENT_EVIDENCE"
        assert origin.document_id == document.id
        assert origin.source_ref == f"sha256:{document.file_hash}"
        assert origin.source_availability == "available"
        assert origin.locator_status == "present"
        assert origin.locator_type == "JSON_POINTER"
        assert json.loads(origin.locator_json or "{}") == {"pointer": "/lines/0/line_total"}
        assert origin.engine_id == "native-json-parser"
        assert origin.engine_version == "1"


def test_derived_line_total_is_not_promoted_to_direct_document_evidence(client, auth):
    response = _upload_invoice(client, auth, number="INV-PAY-TOTAL-DERIVED", explicit_line_total=False)
    assert response.status_code == 201, response.text

    with SessionLocal() as db:
        document = db.scalar(select(Document).where(Document.number == "INV-PAY-TOTAL-DERIVED"))
        assert document is not None
        line = db.scalar(select(DocumentLine).where(DocumentLine.document_id == document.id))
        assert line is not None
        assert line.line_total is not None
        fact = db.scalar(
            select(ProvenanceFact).where(
                ProvenanceFact.tenant_id == document.tenant_id,
                ProvenanceFact.fact_key == f"document_line:{line.id}:line_total",
            )
        )
        assert fact is None
