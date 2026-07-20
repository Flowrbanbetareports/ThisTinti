from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


from app.audit import add_audit, verify_audit_chain
from app.db import SessionLocal
from app.models import Tenant
from app.parsers.xml_invoice import parse_xml


def _upload_json(client, auth, filename: str, payload: dict):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )


def test_bearer_token_is_revoked_by_logout(client):
    registration = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Revocation Test",
            "email": "revoke@example.com",
            "password": "SecurePassword123!",
        },
    )
    token = registration.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_suspended_tenant_invalidates_existing_session(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    with SessionLocal() as db:
        tenant = db.get(Tenant, me["tenant_id"])
        tenant.status = "suspended"
        tenant.security_version += 1
        db.commit()
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_declared_zero_line_total_is_checked(client, auth):
    payload = {
        "document_type": "order",
        "number": "PO-ZERO",
        "supplier_name": "Zero Supplier",
        "lines": [{"sku": "ZERO-1", "quantity": 5, "unit_price": 10, "line_total": 0}],
    }
    uploaded = _upload_json(client, auth, "zero-total.json", payload)
    assert uploaded.status_code == 201, uploaded.text
    cases = client.get("/api/cases", headers=auth).json()
    mismatch = next(case for case in cases if case["case_type"] == "line_total_mismatch")
    assert mismatch["amount_estimate"] == 50.0


def test_manual_attachment_rejects_supplier_mismatch(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-A",
        "supplier_name": "Supplier A",
        "lines": [{"sku": "A-1", "quantity": 1, "unit_price": 10}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-B",
        "supplier_name": "Supplier B",
        "lines": [{"sku": "B-1", "quantity": 1, "unit_price": 10}],
    }
    order_doc = _upload_json(client, auth, "order-a.json", order).json()["document"]
    invoice_doc = _upload_json(client, auth, "invoice-b.json", invoice).json()["document"]
    chains = client.get("/api/chains", headers=auth).json()
    order_chain = next(chain for chain in chains if order_doc["id"] in chain["documents"].get("order", []))
    invoice_chain = next(chain for chain in chains if invoice_doc["id"] in chain["documents"].get("invoice", []))
    assert (
        client.delete(f"/api/chains/{invoice_chain['id']}/documents/{invoice_doc['id']}", headers=auth).status_code
        == 200
    )
    rejected = client.post(
        f"/api/chains/{order_chain['id']}/attach",
        headers=auth,
        json={"document_id": invoice_doc["id"], "role": "invoice"},
    )
    assert rejected.status_code == 409
    assert "supplier" in rejected.json()["detail"].lower()


def test_audit_order_is_independent_from_equal_timestamps(client, auth, monkeypatch):
    me = client.get("/api/auth/me", headers=auth).json()
    fixed = datetime(2026, 7, 19, 12, 0, 0, 123456, tzinfo=timezone.utc)
    monkeypatch.setattr("app.audit.utcnow", lambda: fixed)
    with SessionLocal() as db:
        add_audit(db, me["tenant_id"], "test.same_timestamp.one", me["id"])
        add_audit(db, me["tenant_id"], "test.same_timestamp.two", me["id"])
        db.commit()
        result = verify_audit_chain(db, me["tenant_id"])
    assert result["valid"] is True


def test_confirmation_overrides_order_as_commercial_baseline(client, auth):
    common = {"supplier_name": "Confirm Supplier", "lines": [{"sku": "C-1", "quantity": 1}]}
    payloads = [
        {
            **common,
            "document_type": "order",
            "number": "PO-CONF",
            "lines": [{**common["lines"][0], "unit_price": 10}],
        },
        {
            **common,
            "document_type": "confirmation",
            "number": "CONF-1",
            "references": {"order_numbers": ["PO-CONF"]},
            "lines": [{**common["lines"][0], "unit_price": 12}],
        },
        {
            **common,
            "document_type": "invoice",
            "number": "INV-CONF",
            "references": {"order_numbers": ["PO-CONF"]},
            "lines": [{**common["lines"][0], "unit_price": 13}],
        },
    ]
    for index, payload in enumerate(payloads):
        response = _upload_json(client, auth, f"confirmation-{index}.json", payload)
        assert response.status_code == 201, response.text
    cases = client.get("/api/cases", headers=auth).json()
    price_case = next(case for case in cases if case["case_type"] == "price_over_order")
    assert price_case["amount_estimate"] == 1.0
    assert any(evidence["expected_value"] == "12.0000" for evidence in price_case["evidence"])


def test_sequential_discounts_are_not_summed(client, auth):
    payload = {
        "document_type": "order",
        "number": "PO-DISCOUNT",
        "supplier_name": "Discount Supplier",
        "lines": [
            {
                "sku": "D-1",
                "quantity": 1,
                "unit_price": 100,
                "discounts": [10, 10],
                "line_total": 81,
            }
        ],
    }
    uploaded = _upload_json(client, auth, "sequential-discounts.json", payload)
    assert uploaded.status_code == 201, uploaded.text
    line = uploaded.json()["document"]["lines"][0]
    assert Decimal(str(line["discount_rate"])) == Decimal("19")
    cases = client.get("/api/cases", headers=auth).json()
    assert not any(case["case_type"] == "line_total_mismatch" for case in cases)


def test_fatturapa_references_keep_semantic_container(tmp_path: Path):
    xml = """<?xml version='1.0' encoding='UTF-8'?>
    <FatturaElettronica>
      <FatturaElettronicaHeader>
        <CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>123</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>Supplier</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
      </FatturaElettronicaHeader>
      <FatturaElettronicaBody>
        <DatiGenerali>
          <DatiGeneraliDocumento><TipoDocumento>TD04</TipoDocumento><Divisa>EUR</Divisa><Data>2026-07-19</Data><Numero>NC-1</Numero></DatiGeneraliDocumento>
          <DatiOrdineAcquisto><IdDocumento>PO-1</IdDocumento></DatiOrdineAcquisto>
          <DatiContratto><IdDocumento>CONTRACT-9</IdDocumento></DatiContratto>
          <DatiFattureCollegate><IdDocumento>INV-7</IdDocumento></DatiFattureCollegate>
        </DatiGenerali>
        <DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><Descrizione>Item</Descrizione><Quantita>1</Quantita><PrezzoUnitario>10</PrezzoUnitario><PrezzoTotale>10</PrezzoTotale><AliquotaIVA>22</AliquotaIVA></DettaglioLinee></DatiBeniServizi>
      </FatturaElettronicaBody>
    </FatturaElettronica>"""
    path = tmp_path / "invoice.xml"
    path.write_text(xml, encoding="utf-8")
    parsed = parse_xml(path, {})
    assert parsed.references["order_numbers"] == ["PO-1"]
    assert parsed.references["contract_numbers"] == ["CONTRACT-9"]
    assert parsed.references["invoice_numbers"] == ["INV-7"]


def test_discovered_rules_never_auto_activate_without_human_confirmation():
    from app.services.discovery import _upsert_rule

    with SessionLocal() as db:
        tenant = Tenant(name="Discovery Guardrail")
        db.add(tenant)
        db.flush()
        proposal = _upsert_rule(
            db,
            tenant.id,
            code="field_consistency:serial",
            title="Serial consistency",
            description="Compare serials",
            rationale="High synthetic confidence",
            confidence=0.99,
            threshold=0.92,
            confirmation_threshold=0.68,
            source="discovered",
        )
        assert proposal.status == "needs_confirmation"


def test_postgres_rls_policy_uses_initplan_optimized_tenant_context():
    migration = (
        Path(__file__).resolve().parents[1] / "migrations/versions/c21d9e4a7b63_add_jobs_and_postgres_tenant_guards.py"
    ).read_text(encoding="utf-8")
    assert "(SELECT NULLIF(current_setting('app.current_tenant', true), ''))" in migration
