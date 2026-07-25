from __future__ import annotations

import json

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import ProcessingJob
from scripts.run_worker import run_once


def _upload_order(client, auth, number: str = "RECOVERY-1") -> str:
    payload = {
        "document_type": "order",
        "number": number,
        "supplier_name": "Recovery Supplier",
        "lines": [{"sku": "REC-1", "quantity": 1, "unit_price": 12}],
    }
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("recovery.json", json.dumps(payload).encode(), "application/json")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document"]["id"]


def test_job_list_supports_context_counts_filters_and_search(client, auth):
    document_id = _upload_order(client, auth)
    me = client.get("/api/auth/me", headers=auth).json()
    with SessionLocal() as db:
        failed = ProcessingJob(
            tenant_id=me["tenant_id"],
            created_by=me["id"],
            job_type="reprocess_document",
            status="failed",
            attempts=3,
            max_attempts=3,
            progress=35,
            input_json=json.dumps({"document_id": document_id, "overrides": {"number": "RECOVERY-UPDATED"}}),
            error_message="Rielaborazione interrotta",
        )
        queued = ProcessingJob(
            tenant_id=me["tenant_id"],
            created_by=me["id"],
            job_type="reanalyze_tenant",
            status="queued",
            input_json="{}",
        )
        db.add_all([failed, queued])
        db.commit()
        failed_id = failed.id

    response = client.get("/api/jobs?status=failed&query=RECOVERY-UPDATED&limit=10&offset=0", headers=auth)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert payload["status_counts"]["failed"] == 1
    assert payload["status_counts"]["queued"] == 0
    job = payload["items"][0]
    assert job["id"] == failed_id
    assert job["context"]["document_id"] == document_id
    assert job["can_retry"] is True
    assert job["can_cancel"] is False

    invalid_status = client.get("/api/jobs?status=unknown", headers=auth)
    invalid_type = client.get("/api/jobs?job_type=unknown", headers=auth)
    assert invalid_status.status_code == 422
    assert invalid_type.status_code == 422


def test_failed_reprocess_job_can_be_retried_and_completed(client, auth):
    document_id = _upload_order(client, auth)
    me = client.get("/api/auth/me", headers=auth).json()
    with SessionLocal() as db:
        failed = ProcessingJob(
            tenant_id=me["tenant_id"],
            created_by=me["id"],
            job_type="reprocess_document",
            status="failed",
            attempts=3,
            max_attempts=3,
            input_json=json.dumps({"document_id": document_id, "overrides": {"number": "RECOVERY-UPDATED"}}),
            error_message="Errore precedente simulato",
        )
        db.add(failed)
        db.commit()
        failed_id = failed.id

    retried = client.post(f"/api/jobs/{failed_id}/retry", headers=auth)
    assert retried.status_code == 202, retried.text
    new_job = retried.json()["job"]
    assert new_job["status"] == "queued"
    assert new_job["context"]["document_id"] == document_id
    assert new_job["context"]["retry_of"] == failed_id
    assert new_job["can_cancel"] is True

    assert run_once("pytest-recovery-worker") is True
    completed = client.get(f"/api/jobs/{new_job['id']}", headers=auth)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    document = client.get(f"/api/documents/{document_id}", headers=auth).json()
    assert document["number"] == "RECOVERY-UPDATED"


def test_cancelled_ingest_without_staged_file_is_not_retryable(client, auth):
    payload = {
        "document_type": "order",
        "number": "RECOVERY-CANCEL",
        "lines": [{"sku": "C-1", "quantity": 1, "unit_price": 1}],
    }
    queued = client.post(
        "/api/jobs/documents",
        headers=auth,
        files={"file": ("cancel.json", json.dumps(payload).encode(), "application/json")},
    )
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["job"]["id"]
    cancelled = client.delete(f"/api/jobs/{job_id}", headers=auth)
    assert cancelled.status_code == 200
    assert cancelled.json()["job"]["can_retry"] is False

    retry = client.post(f"/api/jobs/{job_id}/retry", headers=auth)
    assert retry.status_code == 409
    assert "non è più disponibile" in retry.json()["detail"]


def test_failed_ingest_with_rejected_file_can_be_retried(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    rejected = settings.rejected_dir / "recoverable.json"
    rejected.write_text(
        json.dumps(
            {
                "document_type": "order",
                "number": "RECOVERED-INGEST",
                "supplier_name": "Recovery Supplier",
                "lines": [{"sku": "R-1", "quantity": 2, "unit_price": 4}],
            }
        ),
        encoding="utf-8",
    )
    with SessionLocal() as db:
        failed = ProcessingJob(
            tenant_id=me["tenant_id"],
            created_by=me["id"],
            job_type="ingest_document",
            status="failed",
            attempts=3,
            max_attempts=3,
            input_json=json.dumps(
                {
                    "rejected_path": str(rejected),
                    "original_filename": "recoverable.json",
                    "content_type": "application/json",
                    "size_bytes": rejected.stat().st_size,
                    "overrides": {},
                }
            ),
            error_message="Errore precedente simulato",
        )
        db.add(failed)
        db.commit()
        failed_id = failed.id

    listed = client.get(f"/api/jobs?status=failed&query={failed_id}", headers=auth).json()
    assert listed["items"][0]["can_retry"] is True

    retried = client.post(f"/api/jobs/{failed_id}/retry", headers=auth)
    assert retried.status_code == 202, retried.text
    new_job_id = retried.json()["job"]["id"]
    assert run_once("pytest-ingest-recovery-worker") is True
    completed = client.get(f"/api/jobs/{new_job_id}", headers=auth).json()
    assert completed["status"] == "completed"
    assert completed["result"]["document_id"]

    with SessionLocal() as db:
        stored = db.scalar(select(ProcessingJob).where(ProcessingJob.id == new_job_id))
        input_payload = json.loads(stored.input_json)
        assert input_payload["retry_of"] == failed_id
        assert "rejected_path" not in input_payload
