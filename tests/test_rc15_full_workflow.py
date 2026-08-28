from __future__ import annotations

import io
import zipfile
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document, OperationChain, ProcessingJob, Tenant, User
from app.provenance_models import ProvenanceOrigin
from app.services.rc15 import (
    _automatic_document_intake,
    _automatic_job_intake,
    _json,
    _money,
    ensure_practice_for_chain,
    normalize_company_profile,
    record_document_retry,
)
from app.services.rc15_pilot import add_pilot_practice, update_pilot_case


def _identity() -> tuple[str, str]:
    with SessionLocal() as db:
        tenant_id = db.scalar(select(Tenant.id))
        user_id = db.scalar(select(User.id))
        assert tenant_id is not None
        assert user_id is not None
        return tenant_id, user_id


def test_rc15_supervised_workflow_end_to_end(client, auth):
    demo = client.post("/api/demo/load", headers=auth)
    assert demo.status_code == 200, demo.text

    status = client.get("/api/rc15/status", headers=auth)
    assert status.status_code == 200
    assert status.json()["release"] == "RC15 Pilot-Ready"
    assert "integrated_pilot" in status.json()["capabilities"]

    documents = client.get("/api/documents", headers=auth).json()
    assert documents
    document_id = documents[0]["id"]

    intake = client.get("/api/rc15/intake", headers=auth)
    assert intake.status_code == 200
    assert any(item["subject_id"] == document_id for item in intake.json())
    classification = client.post(
        f"/api/rc15/intake/document/{document_id}/classify",
        headers=auth,
        json={
            "state": "review_required",
            "category": "operator_input",
            "phase": "human_review",
            "reason": "Verifica manuale richiesta",
            "note": "Classificazione supervisionata",
        },
    )
    assert classification.status_code == 200, classification.text
    assert classification.json()["classification"]["automatic"] is False
    pending_intake = client.get("/api/rc15/intake?include_success=false", headers=auth)
    assert pending_intake.status_code == 200
    assert any(item["subject_id"] == document_id for item in pending_intake.json())

    tenant_id, user_id = _identity()
    with SessionLocal() as db:
        record_document_retry(db, tenant_id, document_id)
        db.commit()

    cases = client.get("/api/cases", headers=auth).json()
    assert cases
    case_id = cases[0]["id"]
    detail = client.get(f"/api/rc15/cases/{case_id}", headers=auth)
    assert detail.status_code == 200, detail.text
    allowed = detail.json()["allowed_actions"]
    assert allowed
    action = "confirmed" if "confirmed" in allowed else allowed[0]
    transition = client.post(
        f"/api/rc15/cases/{case_id}/transition",
        headers=auth,
        json={"action": action, "note": "Decisione verificata sui documenti"},
    )
    assert transition.status_code == 200, transition.text
    economic = client.put(
        f"/api/rc15/cases/{case_id}/economic",
        headers=auth,
        json={
            "state": "estimated",
            "potential_exposure": "125.50",
            "confirmed_loss": None,
            "currency": "eur",
            "note": "Esposizione potenziale da verificare",
        },
    )
    assert economic.status_code == 200, economic.text
    assert economic.json()["economic"]["potential_exposure"] == 125.5
    assert economic.json()["economic"]["currency"] == "EUR"

    profile = client.get("/api/rc15/company-profile", headers=auth)
    assert profile.status_code == 200
    assert profile.json()["active"]["version"] == 1
    profile_payload = {
        "label": "Profilo operativo RC15",
        "config": {
            "default_currency": "EUR",
            "rounding_decimals": 2,
            "price_tolerance_percent": 2.5,
            "quantity_tolerance_percent": 1.0,
            "unit_aliases": {"pezzi": "PCE", "kg": "KGM"},
            "significant_terms": ["garanzia", "classe a"],
        },
    }
    created_profile = client.post(
        "/api/rc15/company-profile/versions",
        headers=auth,
        json=profile_payload,
    )
    assert created_profile.status_code == 201, created_profile.text
    assert created_profile.json()["created"] is True
    duplicate_profile = client.post(
        "/api/rc15/company-profile/versions",
        headers=auth,
        json=profile_payload,
    )
    assert duplicate_profile.status_code == 201
    assert duplicate_profile.json()["created"] is False
    versions = client.get("/api/rc15/company-profile/versions", headers=auth)
    assert versions.status_code == 200
    assert len(versions.json()) == 2

    overview = client.get("/api/operational/overview", headers=auth).json()
    chain_id = overview["practices"][0]["chain_id"]
    practice_response = client.post(
        f"/api/rc15/practices/from-chain/{chain_id}",
        headers=auth,
        json={},
    )
    assert practice_response.status_code == 201, practice_response.text
    practice_id = practice_response.json()["practice"]["id"]
    practice_documents = practice_response.json()["practice"]["documents"]
    assert practice_documents
    assert practice_response.json()["practice"]["text_differences"] is not None
    practice_document_ids = [item["id"] for item in practice_documents]
    with SessionLocal() as db:
        practice_origins = list(
            db.scalars(
                select(ProvenanceOrigin).where(
                    ProvenanceOrigin.tenant_id == tenant_id,
                    ProvenanceOrigin.document_id.in_(practice_document_ids),
                    ProvenanceOrigin.origin_type == "DOCUMENT_EVIDENCE",
                )
            )
        )
        base_origins = [item for item in practice_origins if item.locator_status == "not_applicable"]
        assert len(practice_origins) >= len(practice_document_ids)
        assert len(base_origins) == len(practice_document_ids)
        assert {item.document_id for item in base_origins} == set(practice_document_ids)
        provenance_origin_ids = [item.id for item in practice_origins]
        provenance_source_refs = {item.source_ref for item in practice_origins}
        provenance_locator_states = {
            item.id: (item.locator_status, item.locator_type, item.locator_json) for item in practice_origins
        }
        assert all(item.source_availability == "available" for item in practice_origins)

    practices = client.get("/api/rc15/practices", headers=auth)
    assert practices.status_code == 200
    assert any(item["id"] == practice_id for item in practices.json())
    practice_detail = client.get(f"/api/rc15/practices/{practice_id}", headers=auth)
    assert practice_detail.status_code == 200
    archived = client.post(f"/api/rc15/practices/{practice_id}/archive", headers=auth)
    assert archived.status_code == 200
    assert archived.json()["practice"]["status"] == "archived"
    restored = client.post(f"/api/rc15/practices/{practice_id}/restore", headers=auth)
    assert restored.status_code == 200
    assert restored.json()["practice"]["status"] == "active"

    exported = client.get(
        f"/api/rc15/practices/{practice_id}/export?include_originals=true",
        headers=auth,
    )
    assert exported.status_code == 200, exported.text
    assert exported.headers["x-thistinti-manifest-sha256"]
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        names = archive.namelist()
        assert "practice.json" in names
        assert "manifest.json" in names
        assert any(name.startswith("originals/") for name in names)

    invalid_reviewers = client.post(
        "/api/rc15/pilots",
        headers=auth,
        json={
            "name": "Pilot non valido",
            "authorization_reference": "AUTH-INVALID",
            "reviewer_primary": "REV-A",
            "reviewer_secondary": "rev-a",
            "scope": "Perimetro di prova sufficientemente dettagliato",
        },
    )
    assert invalid_reviewers.status_code == 422

    pilot_response = client.post(
        "/api/rc15/pilots",
        headers=auth,
        json={
            "name": "Pilot controllato RC15",
            "authorization_reference": "AUTH-RC15-001",
            "reviewer_primary": "Revisore Alfa",
            "reviewer_secondary": "Revisore Beta",
            "scope": "Trenta pratiche sintetiche isolate usate soltanto per regressione tecnica.",
        },
    )
    assert pilot_response.status_code == 201, pilot_response.text
    pilot_id = pilot_response.json()["id"]

    practice_ids: list[str] = []
    pilot_case_ids: list[str] = []
    truth = {"findings": [], "notes": "Nessuna anomalia attesa"}
    with SessionLocal() as db:
        for index in range(30):
            chain = OperationChain(
                tenant_id=tenant_id,
                reference_key=f"RC15-PILOT-{index:02d}",
            )
            db.add(chain)
            db.flush()
            practice, created = ensure_practice_for_chain(
                db,
                tenant_id,
                user_id,
                chain.id,
            )
            assert created is True
            pilot_case = add_pilot_practice(db, tenant_id, pilot_id, practice.id)
            update_pilot_case(
                db,
                tenant_id,
                pilot_id,
                pilot_case.id,
                reviewer_primary=truth,
                reviewer_secondary=truth,
                adjudicated=None,
                manual_seconds=100.0 + index,
                assisted_seconds=50.0 + index,
                user_score=4,
                notes="Misurazione sintetica di regressione",
            )
            practice_ids.append(practice.id)
            pilot_case_ids.append(pilot_case.id)
        db.commit()

    duplicate_add = client.post(
        f"/api/rc15/pilots/{pilot_id}/practices",
        headers=auth,
        json={"practice_id": practice_ids[0]},
    )
    assert duplicate_add.status_code == 201
    assert duplicate_add.json()["case_id"] == pilot_case_ids[0]

    updated_case = client.patch(
        f"/api/rc15/pilots/{pilot_id}/cases/{pilot_case_ids[0]}",
        headers=auth,
        json={
            "reviewer_primary": truth,
            "reviewer_secondary": truth,
            "manual_seconds": 120.0,
            "assisted_seconds": 55.0,
            "user_score": 5,
            "notes": "Aggiornamento verificato",
        },
    )
    assert updated_case.status_code == 200, updated_case.text
    assert updated_case.json()["pilot"]["case_count"] == 30

    pilots = client.get("/api/rc15/pilots", headers=auth)
    assert pilots.status_code == 200
    assert any(item["id"] == pilot_id for item in pilots.json())
    internal_pilot = client.get(
        f"/api/rc15/pilots/{pilot_id}?include_ground_truth=true",
        headers=auth,
    )
    assert internal_pilot.status_code == 200
    assert internal_pilot.json()["authorization_reference"] == "AUTH-RC15-001"

    frozen = client.post(f"/api/rc15/pilots/{pilot_id}/freeze", headers=auth)
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["status"] == "frozen"
    assert frozen.json()["ground_truth_hash"]

    run = client.post(f"/api/rc15/pilots/{pilot_id}/run", headers=auth)
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "completed"
    assert run.json()["result"]["metrics"]["false_negatives"] == 0
    assert run.json()["result"]["metrics"]["measurement_missing"] == 0
    assert run.json()["result"]["decision"] == "idoneo_con_revisione_umana"

    json_report = client.get(f"/api/rc15/pilots/{pilot_id}/report", headers=auth)
    assert json_report.status_code == 200
    assert json_report.headers["content-type"].startswith("application/json")
    markdown_report = client.get(
        f"/api/rc15/pilots/{pilot_id}/report?format=markdown",
        headers=auth,
    )
    assert markdown_report.status_code == 200
    assert "ThisTinti RC15" in markdown_report.text
    assert "Non è una certificazione" in markdown_report.text

    archived_pilot = client.post(f"/api/rc15/pilots/{pilot_id}/archive", headers=auth)
    assert archived_pilot.status_code == 200
    archived_list = client.get("/api/rc15/pilots?include_archived=true", headers=auth)
    assert archived_list.status_code == 200
    assert any(item["id"] == pilot_id and item["status"] == "archived" for item in archived_list.json())

    bad_delete = client.request(
        "DELETE",
        f"/api/rc15/practices/{practice_id}",
        headers=auth,
        json={"confirm_practice_id": "wrong-id"},
    )
    assert bad_delete.status_code == 422
    deleted = client.request(
        "DELETE",
        f"/api/rc15/practices/{practice_id}",
        headers=auth,
        json={"confirm_practice_id": practice_id},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["tombstone_hash"]
    assert deleted.json()["document_count"] > 0
    deleted_list = client.get("/api/rc15/practices?include_deleted=true", headers=auth)
    assert deleted_list.status_code == 200
    tombstone = next(item for item in deleted_list.json() if item["id"] == practice_id)
    assert tombstone["status"] == "deleted"
    assert tombstone["chain_id"] is None
    with SessionLocal() as db:
        deleted_origins = list(
            db.scalars(select(ProvenanceOrigin).where(ProvenanceOrigin.id.in_(provenance_origin_ids)))
        )
        assert len(deleted_origins) == len(provenance_origin_ids)
        assert {item.source_ref for item in deleted_origins} == provenance_source_refs
        assert all(item.document_id is None for item in deleted_origins)
        assert all(item.source_availability == "deleted_by_retention" for item in deleted_origins)
        assert {
            item.id: (item.locator_status, item.locator_type, item.locator_json) for item in deleted_origins
        } == provenance_locator_states


def test_rc15_helpers_and_validation_branches():
    assert _json("not-json", {"fallback": True}) == {"fallback": True}
    assert _money(None) is None
    assert _money(Decimal("12.345")) == 12.34

    parsed = Document(parse_status="parsed", parse_message=None)
    assert _automatic_document_intake(parsed)["state"] == "acquired"
    parsed.parse_status = "review_required"
    parsed.parse_message = "Serve controllo"
    assert _automatic_document_intake(parsed)["category"] == "degraded"
    parsed.parse_message = None
    assert _automatic_document_intake(parsed)["category"] == "operator_input"
    parsed.parse_status = "queued"
    assert _automatic_document_intake(parsed)["state"] == "review_required"

    for message, expected in (
        ("malware scanner blocked", "blocked"),
        ("unsupported format", "out_of_scope"),
        ("OCR failed", "not_acquired"),
        ("generic parser failure", "not_acquired"),
    ):
        job = ProcessingJob(error_message=message)
        assert _automatic_job_intake(job)["state"] == expected

    normalized = normalize_company_profile(
        {
            "default_currency": " usd ",
            "rounding_decimals": 3,
            "price_tolerance_percent": 5,
            "quantity_tolerance_percent": 2,
            "unit_aliases": {" Pezzi ": " pce ", "": "skip"},
            "significant_terms": [" Garanzia ", "garanzia", "Classe A"],
        }
    )
    assert normalized["default_currency"] == "USD"
    assert normalized["unit_aliases"] == {"pezzi": "PCE"}
    assert normalized["significant_terms"] == ["classe a", "garanzia"]

    with pytest.raises(ValueError):
        normalize_company_profile({"rounding_decimals": 7})
    with pytest.raises(ValueError):
        normalize_company_profile({"price_tolerance_percent": 101})
    with pytest.raises(ValueError):
        normalize_company_profile({"quantity_tolerance_percent": -1})
    with pytest.raises(ValueError):
        normalize_company_profile({"unit_aliases": ["bad"]})
    with pytest.raises(ValueError):
        normalize_company_profile({"significant_terms": "not-a-list"})
