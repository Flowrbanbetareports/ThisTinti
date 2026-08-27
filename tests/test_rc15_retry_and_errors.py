from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

import app.rc15_api as rc15_api
from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, Tenant, User
from app.parsers import ParseError
from app.services.rc15 import (
    _automatic_document_intake,
    classify_intake,
    set_economic_assessment,
    transition_case,
)


def _ids() -> tuple[str, str]:
    with SessionLocal() as db:
        tenant_id = db.scalar(select(Tenant.id))
        user_id = db.scalar(select(User.id))
        assert tenant_id is not None
        assert user_id is not None
        return tenant_id, user_id


def test_retry_records_failure_then_recovers_without_hiding_technical_outcome(client, auth, monkeypatch):
    loaded = client.post("/api/demo/load", headers=auth)
    assert loaded.status_code == 200, loaded.text
    document = client.get("/api/documents", headers=auth).json()[0]
    document_id = document["id"]

    missing = client.post("/api/rc15/intake/documents/not-a-document/retry", headers=auth, json={})
    assert missing.status_code == 404

    def fail_reprocess(db, item, overrides):
        item.parse_status = "failed"
        item.parse_message = "Parser RC15 intenzionalmente fallito nel test"
        raise ParseError("Rielaborazione non riuscita", reason="Limite parser verificato")

    monkeypatch.setattr(rc15_api, "reprocess_document", fail_reprocess)
    first_failure = client.post(
        f"/api/rc15/intake/documents/{document_id}/retry",
        headers=auth,
        json={"document_type": "invoice", "supplier_name": "Supplier test", "number": "INV-RC15"},
    )
    assert first_failure.status_code == 422, first_failure.text
    intake = client.get("/api/rc15/intake", headers=auth).json()
    failed = next(item for item in intake if item["subject_id"] == document_id)
    assert failed["parse_status"] == "failed"
    assert failed["classification"]["state"] == "not_acquired"
    assert failed["classification"]["category"] == "parser_limit"

    second_failure = client.post(
        f"/api/rc15/intake/documents/{document_id}/retry",
        headers=auth,
        json={"document_date": "2026-08-27"},
    )
    assert second_failure.status_code == 422

    def succeed_reprocess(db, item, overrides):
        item.parse_status = "parsed"
        item.parse_message = None
        item.confidence = 0.91
        return item

    monkeypatch.setattr(rc15_api, "reprocess_document", succeed_reprocess)
    recovered = client.post(
        f"/api/rc15/intake/documents/{document_id}/retry",
        headers=auth,
        json={"document_type": "invoice", "document_date": "2026-08-27"},
    )
    assert recovered.status_code == 200, recovered.text
    payload = recovered.json()["document"]
    assert payload["parse_status"] == "parsed"
    assert payload["classification"]["state"] == "acquired"
    assert payload["confidence"] == pytest.approx(0.91)

    audit = client.get("/api/audit", headers=auth).json()
    actions = {item["action"] for item in audit}
    assert "rc15.intake_retry_failed" in actions
    assert "rc15.intake_retried" in actions


def test_rc15_api_maps_not_found_and_conflict_paths(client, auth):
    loaded = client.post("/api/demo/load", headers=auth)
    assert loaded.status_code == 200

    assert client.get("/api/rc15/cases/missing", headers=auth).status_code == 404
    assert (
        client.post(
            "/api/rc15/cases/missing/transition",
            headers=auth,
            json={"action": "confirmed", "note": "Motivo valido"},
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/api/rc15/cases/missing/economic",
            headers=auth,
            json={"state": "unknown", "currency": "EUR", "note": "Non disponibile"},
        ).status_code
        == 404
    )

    assert client.post("/api/rc15/practices/from-chain/missing", headers=auth, json={}).status_code == 404
    assert client.get("/api/rc15/practices/missing", headers=auth).status_code == 404
    assert client.post("/api/rc15/practices/missing/archive", headers=auth).status_code == 404
    assert client.post("/api/rc15/practices/missing/restore", headers=auth).status_code == 404
    assert client.get("/api/rc15/practices/missing/export", headers=auth).status_code == 404
    assert (
        client.request(
            "DELETE",
            "/api/rc15/practices/missing",
            headers=auth,
            json={"confirm_practice_id": "missing"},
        ).status_code
        == 404
    )

    assert client.get("/api/rc15/pilots/missing", headers=auth).status_code == 404
    assert client.get("/api/rc15/pilots/missing/report", headers=auth).status_code == 404
    assert client.post("/api/rc15/pilots/missing/archive", headers=auth).status_code == 404
    assert (
        client.post(
            "/api/rc15/pilots/missing/practices",
            headers=auth,
            json={"practice_id": "missing"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/rc15/pilots/missing/cases/missing",
            headers=auth,
            json={"manual_seconds": 10},
        ).status_code
        == 404
    )

    pilot = client.post(
        "/api/rc15/pilots",
        headers=auth,
        json={
            "name": "Pilot error paths",
            "authorization_reference": "AUTH-ERROR-1",
            "reviewer_primary": "Reviewer A",
            "reviewer_secondary": "Reviewer B",
            "scope": "Pilot sintetico per verificare i blocchi di stato RC15.",
        },
    )
    assert pilot.status_code == 201, pilot.text
    pilot_id = pilot.json()["id"]
    assert client.post(f"/api/rc15/pilots/{pilot_id}/freeze", headers=auth).status_code == 409
    assert client.post(f"/api/rc15/pilots/{pilot_id}/run", headers=auth).status_code == 409
    assert (
        client.post(
            f"/api/rc15/pilots/{pilot_id}/practices",
            headers=auth,
            json={"practice_id": "missing"},
        ).status_code
        == 404
    )


def test_rc15_service_validation_paths(client, auth):
    loaded = client.post("/api/demo/load", headers=auth)
    assert loaded.status_code == 200
    tenant_id, user_id = _ids()

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.tenant_id == tenant_id))
        assert case is not None

        with pytest.raises(LookupError):
            transition_case(db, tenant_id, user_id, "missing", "confirmed", "Motivo valido")
        with pytest.raises(ValueError):
            transition_case(db, tenant_id, user_id, case.id, "confirmed", "x")
        with pytest.raises(ValueError):
            transition_case(db, tenant_id, user_id, case.id, "invalid", "Motivo valido")

        if case.status != "confirmed":
            if case.status == "open":
                transition_case(db, tenant_id, user_id, case.id, "confirmed", "Conferma per test")
            elif case.status == "needs_review":
                transition_case(db, tenant_id, user_id, case.id, "confirmed", "Conferma per test")
        if case.status == "confirmed":
            with pytest.raises(ValueError):
                transition_case(db, tenant_id, user_id, case.id, "confirmed", "Conferma duplicata")

        with pytest.raises(LookupError):
            set_economic_assessment(
                db,
                tenant_id,
                user_id,
                "missing",
                state="unknown",
                potential_exposure=None,
                confirmed_loss=None,
                currency="EUR",
                note="Non disponibile",
            )
        invalid_economics = (
            {
                "state": "estimated",
                "potential_exposure": Decimal("-1"),
                "confirmed_loss": None,
                "currency": "EUR",
                "note": "Negativo",
            },
            {
                "state": "loss_confirmed",
                "potential_exposure": None,
                "confirmed_loss": Decimal("-1"),
                "currency": "EUR",
                "note": "Negativo",
            },
            {
                "state": "not-a-state",
                "potential_exposure": None,
                "confirmed_loss": None,
                "currency": "EUR",
                "note": "Stato errato",
            },
            {
                "state": "unknown",
                "potential_exposure": Decimal("1"),
                "confirmed_loss": None,
                "currency": "EUR",
                "note": "Ambiguo",
            },
            {
                "state": "estimated",
                "potential_exposure": None,
                "confirmed_loss": None,
                "currency": "EUR",
                "note": "Senza importo",
            },
            {
                "state": "confirmed_zero",
                "potential_exposure": None,
                "confirmed_loss": Decimal("1"),
                "currency": "EUR",
                "note": "Zero errato",
            },
            {
                "state": "loss_confirmed",
                "potential_exposure": None,
                "confirmed_loss": Decimal("0"),
                "currency": "EUR",
                "note": "Perdita errata",
            },
            {"state": "unknown", "potential_exposure": None, "confirmed_loss": None, "currency": "EUR", "note": "x"},
            {
                "state": "unknown",
                "potential_exposure": None,
                "confirmed_loss": None,
                "currency": "E",
                "note": "Valuta errata",
            },
        )
        for values in invalid_economics:
            with pytest.raises(ValueError):
                set_economic_assessment(db, tenant_id, user_id, case.id, **values)

        with pytest.raises(ValueError):
            classify_intake(
                db,
                tenant_id,
                user_id,
                subject_type="invalid",
                subject_id="missing",
                state="review_required",
                category="operator_input",
                phase=None,
                reason="Motivo valido",
                note=None,
            )
        with pytest.raises(ValueError):
            classify_intake(
                db,
                tenant_id,
                user_id,
                subject_type="document",
                subject_id="missing",
                state="invalid",
                category="operator_input",
                phase=None,
                reason="Motivo valido",
                note=None,
            )
        with pytest.raises(LookupError):
            classify_intake(
                db,
                tenant_id,
                user_id,
                subject_type="document",
                subject_id="missing",
                state="review_required",
                category="operator_input",
                phase=None,
                reason="Motivo valido",
                note=None,
            )


def test_failed_document_intake_categories_preserve_failure_state():
    cases = (
        ("malware rilevato dallo scanner di sicurezza", "blocked", "security_block"),
        ("OCR non disponibile per immagine scansionata", "not_acquired", "degraded"),
        ("Formato non supportato", "out_of_scope", "out_of_scope"),
        ("Errore parser non classificato", "not_acquired", "parser_limit"),
    )
    for message, expected_state, expected_category in cases:
        document = Document(parse_status="failed", parse_message=message, source_filename="test.pdf")
        result = _automatic_document_intake(document)
        assert result["state"] == expected_state
        assert result["category"] == expected_category
        assert result["automatic"] is True
