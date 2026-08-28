from __future__ import annotations

import json
from types import SimpleNamespace

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document
from app.provenance_models import ProvenanceFact, ProvenanceOrigin
from app.services.ingestion import _record_direct_source_facts


def _payload(*, number: str, currency: str | None) -> bytes:
    data = {
        "document_type": "order",
        "number": number,
        "document_date": "2026-08-28",
        "supplier_name": "Direct Source Facts Supplier",
        "lines": [
            {
                "line_no": 1,
                "sku": f"ITEM-{number}",
                "description": "Direct evidence fixture",
                "quantity": 1,
                "unit_price": 10,
                "discount_rate": 0,
                "tax_rate": 22,
                "line_total": 10,
            }
        ],
    }
    if currency is not None:
        data["currency"] = currency
    return json.dumps(data).encode("utf-8")


def _upload(client, auth, *, number: str, currency: str | None):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (f"{number}.json", _payload(number=number, currency=currency), "application/json")},
    )


def _facts_for_document(db, document_id: str) -> list[ProvenanceFact]:
    return list(
        db.scalars(
            select(ProvenanceFact)
            .where(ProvenanceFact.fact_key.like(f"document:{document_id}:%"))
            .order_by(ProvenanceFact.fact_key, ProvenanceFact.version)
        )
    )


def test_explicit_json_currency_is_recorded_as_direct_document_evidence(client, auth):
    response = _upload(client, auth, number="FACT-CURRENCY-1", currency="usd")
    assert response.status_code == 201, response.text
    document_id = response.json()["document"]["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        assert document.currency == "USD"
        facts = _facts_for_document(db, document_id)
        assert {(fact.fact_type, fact.value_json) for fact in facts} == {
            ("document.number", '"FACT-CURRENCY-1"'),
            ("document.currency", '"USD"'),
        }
        currency_fact = next(fact for fact in facts if fact.fact_type == "document.currency")
        origin = db.get(ProvenanceOrigin, currency_fact.origin_id)
        assert origin is not None
        assert origin.origin_type == "DOCUMENT_EVIDENCE"
        assert origin.source_availability == "available"
        assert origin.locator_status == "present"
        assert origin.locator_type == "JSON_POINTER"
        assert json.loads(origin.locator_json) == {"pointer": "/currency"}
        assert origin.engine_id == "native-json-parser"
        assert origin.engine_version == "1"


def test_defaulted_json_currency_does_not_create_document_evidence_fact(client, auth):
    response = _upload(client, auth, number="FACT-CURRENCY-DEFAULT", currency=None)
    assert response.status_code == 201, response.text
    document_id = response.json()["document"]["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        assert document.currency == "EUR"
        facts = _facts_for_document(db, document_id)
        assert [fact.fact_type for fact in facts] == ["document.number"]


def test_direct_source_fact_recording_is_idempotent_and_versions_changed_source_value(client, auth):
    response = _upload(client, auth, number="FACT-CURRENCY-VERSION", currency="USD")
    assert response.status_code == 201, response.text
    document_id = response.json()["document"]["id"]

    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        parsed = SimpleNamespace(
            source_locators={
                "currency": {
                    "locator_type": "JSON_POINTER",
                    "pointer": "/currency",
                    "engine_id": "native-json-parser",
                    "engine_version": "1",
                }
            }
        )

        _record_direct_source_facts(db, document.tenant_id, document, parsed, document.file_hash)
        db.flush()
        currency_facts = list(
            db.scalars(
                select(ProvenanceFact)
                .where(ProvenanceFact.fact_key == f"document:{document.id}:currency")
                .order_by(ProvenanceFact.version)
            )
        )
        assert [fact.version for fact in currency_facts] == [1]

        document.currency = "GBP"
        _record_direct_source_facts(db, document.tenant_id, document, parsed, document.file_hash)
        db.flush()
        currency_facts = list(
            db.scalars(
                select(ProvenanceFact)
                .where(ProvenanceFact.fact_key == f"document:{document.id}:currency")
                .order_by(ProvenanceFact.version)
            )
        )
        assert [fact.version for fact in currency_facts] == [1, 2]
        assert [fact.value_json for fact in currency_facts] == ['"USD"', '"GBP"']
        assert currency_facts[1].supersedes_fact_id == currency_facts[0].id
