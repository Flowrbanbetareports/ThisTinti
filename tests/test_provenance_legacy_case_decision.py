from __future__ import annotations

import json
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db import SessionLocal
from app.legacy_cases_api import _locked_case_query
from app.models import DiscrepancyCase, ReviewDecision
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment
from app.services.finding_provenance import _supporting_number_facts
from app.services.judgment_provenance import record_judgment_provenance, resolve_reviewer_identity


def _payload(*, document_type: str, number: str, currency: str, order_number: str | None = None) -> bytes:
    data: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-29",
        "supplier_name": "Legacy Decision Provenance Supplier",
        "supplier_vat": "IT00000000031",
        "currency": currency,
        "lines": [
            {
                "line_no": 1,
                "sku": "LEGACY-CUR",
                "description": "Legacy decision provenance item",
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


def _upload_currency_mismatch(client, auth, *, suffix: str) -> tuple[str, str]:
    order_number = f"PO-LEGACY-CUR-{suffix}"
    order = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"order-{suffix}.json",
                _payload(document_type="order", number=order_number, currency="EUR"),
                "application/json",
            )
        },
    )
    invoice = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"invoice-{suffix}.json",
                _payload(
                    document_type="invoice",
                    number=f"INV-LEGACY-CUR-{suffix}",
                    currency="USD",
                    order_number=order_number,
                ),
                "application/json",
            )
        },
    )
    assert order.status_code == 201, order.text
    assert invoice.status_code == 201, invoice.text

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "currency_mismatch"))
        assert case is not None
        finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert finding is not None
        return case.id, finding.id


def test_case_decision_query_serializes_conflicting_writers_on_postgres():
    compiled = str(_locked_case_query(case_id="case-1", tenant_id="tenant-1").compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in compiled


def test_legacy_case_decision_records_previous_state_and_exact_judgment(client, auth):
    case_id, finding_id = _upload_currency_mismatch(client, auth, suffix="USER")

    response = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Explicit source currencies verified."},
    )
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert judgment is not None
        assert judgment.decision == "confirmed"
        assert judgment.previous_state == "open"
        assert judgment.reviewer_ref.startswith("user:")
        assert judgment.reviewer_user_id is not None

        decision = db.scalar(select(ReviewDecision).where(ReviewDecision.id == judgment.review_decision_id))
        assert decision is not None
        repeated = record_judgment_provenance(
            db,
            tenant_id=judgment.tenant_id,
            case_id=case_id,
            review_decision=decision,
            reviewer_ref=judgment.reviewer_ref,
            reviewer_user_id=judgment.reviewer_user_id,
            previous_state=judgment.previous_state,
        )
        assert repeated is not None
        assert repeated.id == judgment.id


def test_legacy_case_decision_preserves_api_credential_identity_without_user_fk(client, auth):
    case_id, finding_id = _upload_currency_mismatch(client, auth, suffix="API")
    created = client.post(
        "/api/api-credentials",
        headers=auth,
        json={"name": "Legacy review bot", "role": "reviewer", "scopes": ["read", "review"]},
    )
    assert created.status_code == 201, created.text
    credential = created.json()
    api_auth = {"Authorization": f"Bearer {credential['token']}"}

    response = client.post(
        f"/api/cases/{case_id}/decision",
        headers=api_auth,
        json={"decision": "confirmed", "note": "Credential-supervised currency review."},
    )
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        decision = db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id))
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert decision is not None
        assert decision.user_id is None
        assert judgment is not None
        assert judgment.review_decision_id == decision.id
        assert judgment.reviewer_ref == f"api_credential:{credential['id']}"
        assert judgment.reviewer_user_id is None
        assert judgment.previous_state == "open"


def test_p1_case_decision_rolls_back_when_judgment_provenance_cannot_bind(client, auth, monkeypatch):
    case_id, finding_id = _upload_currency_mismatch(client, auth, suffix="STALE")

    monkeypatch.setattr("app.legacy_cases_api.record_judgment_provenance", lambda *args, **kwargs: None)
    response = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Must not commit without exact-current support."},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Case decision requires exact-current provenance support"

    with SessionLocal() as db:
        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == "open"
        assert db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id)) is None
        assert db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)) is None


def test_reviewer_identity_and_malformed_finding_key_fail_closed():
    with SessionLocal() as db:
        assert resolve_reviewer_identity(db, tenant_id="missing-tenant", actor_id=None) == (None, None)
        assert resolve_reviewer_identity(db, tenant_id="missing-tenant", actor_id="missing-actor") == (None, None)
        assert (
            _supporting_number_facts(
                db,
                chain=SimpleNamespace(tenant_id="missing-tenant"),
                finding_key="malformed",
                all_documents=[],
            )
            == []
        )
