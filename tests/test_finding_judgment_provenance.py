from __future__ import annotations

import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, ReviewDecision, User
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment


def _order_payload(number: str, *, suffix: str) -> bytes:
    return json.dumps(
        {
            "document_type": "order",
            "number": number,
            "document_date": "2026-08-28",
            "supplier_name": "Judgment Provenance Supplier",
            "supplier_vat": "IT00000000002",
            "lines": [
                {
                    "line_no": 1,
                    "sku": f"JUD-{suffix}",
                    "description": f"Judgment item {suffix}",
                    "quantity": 1,
                    "unit_price": 12,
                    "discount_rate": 0,
                    "tax_rate": 22,
                    "line_total": 12,
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _upload(
    client,
    auth,
    *,
    filename: str,
    source_number: str,
    suffix: str,
    override_number: str | None = None,
):
    data = {"number": override_number} if override_number is not None else {}
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, _order_payload(source_number, suffix=suffix), "application/json")},
        data=data,
    )
    assert response.status_code == 201, response.text
    return response


def _duplicate_case() -> DiscrepancyCase:
    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "duplicate_document_number"))
        assert case is not None
        db.expunge(case)
        return case


def _transition(client, auth, case_id: str, action: str, note: str):
    response = client.post(
        f"/api/rc15/cases/{case_id}/transition",
        headers=auth,
        json={"action": action, "note": note},
    )
    assert response.status_code == 200, response.text
    return response


def test_human_judgment_links_review_decision_to_current_finding(client, auth):
    _upload(client, auth, filename="judgment-a.json", source_number="JUD-100", suffix="A")
    _upload(client, auth, filename="judgment-b.json", source_number="JUD-100", suffix="B")
    case = _duplicate_case()

    _transition(client, auth, case.id, "confirmed", "Duplicato confermato sui documenti sorgente")

    with SessionLocal() as db:
        user_id = db.scalar(select(User.id))
        finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        decision = db.scalar(
            select(ReviewDecision).where(
                ReviewDecision.tenant_id == case.tenant_id,
                ReviewDecision.case_id == case.id,
            )
        )
        judgment = db.scalar(
            select(ProvenanceJudgment).where(
                ProvenanceJudgment.tenant_id == case.tenant_id,
                ProvenanceJudgment.review_decision_id == decision.id,
            )
        )
        assert user_id is not None
        assert finding is not None
        assert decision is not None
        assert judgment is not None
        assert judgment.finding_id == finding.id
        assert judgment.reviewer_ref == f"user:{user_id}"
        assert judgment.reviewer_user_id == user_id
        assert judgment.decision == "confirmed"
        assert judgment.reason == "Duplicato confermato sui documenti sorgente"
        assert judgment.previous_state == "open"


def test_human_judgment_provenance_is_fail_closed_without_finding(client, auth):
    _upload(client, auth, filename="judgment-mixed-a.json", source_number="JUD-MIX", suffix="A")
    _upload(
        client,
        auth,
        filename="judgment-mixed-b.json",
        source_number="SOURCE-ONLY",
        suffix="B",
        override_number="JUD-MIX",
    )
    case = _duplicate_case()

    with SessionLocal() as db:
        finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert finding is None

    transitioned = _transition(client, auth, case.id, "confirmed", "Decisione valida ma finding non provabile")
    assert transitioned.json()["status"] == "confirmed"

    with SessionLocal() as db:
        decision = db.scalar(
            select(ReviewDecision).where(
                ReviewDecision.tenant_id == case.tenant_id,
                ReviewDecision.case_id == case.id,
            )
        )
        judgments = list(
            db.scalars(
                select(ProvenanceJudgment).where(
                    ProvenanceJudgment.tenant_id == case.tenant_id,
                )
            )
        )
        assert decision is not None
        assert judgments == []


def test_each_judgment_stays_linked_to_finding_version_seen_at_decision_time(client, auth):
    _upload(client, auth, filename="judgment-version-a.json", source_number="JUD-VER", suffix="A")
    _upload(client, auth, filename="judgment-version-b.json", source_number="JUD-VER", suffix="B")
    case = _duplicate_case()

    _transition(client, auth, case.id, "needs_review", "Prima revisione sulla versione iniziale")

    with SessionLocal() as db:
        first_finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
                ProvenanceFinding.version == 1,
            )
        )
        first_judgment = db.scalar(
            select(ProvenanceJudgment).where(ProvenanceJudgment.tenant_id == case.tenant_id)
        )
        assert first_finding is not None
        assert first_judgment is not None
        assert first_judgment.finding_id == first_finding.id

    _upload(client, auth, filename="judgment-version-c.json", source_number="JUD-VER", suffix="C")

    with SessionLocal() as db:
        findings = list(
            db.scalars(
                select(ProvenanceFinding)
                .where(
                    ProvenanceFinding.tenant_id == case.tenant_id,
                    ProvenanceFinding.case_id == case.id,
                )
                .order_by(ProvenanceFinding.version)
            )
        )
        assert [item.version for item in findings] == [1, 2]
        second_finding_id = findings[1].id

    _transition(client, auth, case.id, "confirmed", "Conferma sulla versione aggiornata del finding")

    with SessionLocal() as db:
        judgments = list(
            db.scalars(
                select(ProvenanceJudgment)
                .where(ProvenanceJudgment.tenant_id == case.tenant_id)
                .order_by(ProvenanceJudgment.created_at)
            )
        )
        assert len(judgments) == 2
        assert judgments[0].finding_id != second_finding_id
        assert judgments[1].finding_id == second_finding_id
        assert judgments[0].previous_state == "open"
        assert judgments[1].previous_state == "needs_review"


def test_api_reviewer_uses_credential_identity_without_user_foreign_key(client, auth):
    _upload(client, auth, filename="judgment-api-a.json", source_number="JUD-API", suffix="A")
    _upload(client, auth, filename="judgment-api-b.json", source_number="JUD-API", suffix="B")
    case = _duplicate_case()

    created = client.post(
        "/api/api-credentials",
        headers=auth,
        json={"name": "Review bot", "role": "reviewer", "scopes": ["read", "review"]},
    )
    assert created.status_code == 201, created.text
    credential = created.json()
    api_auth = {"Authorization": f"Bearer {credential['token']}"}

    _transition(client, api_auth, case.id, "confirmed", "Conferma supervisionata tramite credenziale API")

    with SessionLocal() as db:
        decision = db.scalar(
            select(ReviewDecision).where(
                ReviewDecision.tenant_id == case.tenant_id,
                ReviewDecision.case_id == case.id,
            )
        )
        judgment = db.scalar(
            select(ProvenanceJudgment).where(
                ProvenanceJudgment.tenant_id == case.tenant_id,
                ProvenanceJudgment.review_decision_id == decision.id,
            )
        )
        assert decision is not None
        assert decision.user_id is None
        assert judgment is not None
        assert judgment.reviewer_ref == f"api_credential:{credential['id']}"
        assert judgment.reviewer_user_id is None
