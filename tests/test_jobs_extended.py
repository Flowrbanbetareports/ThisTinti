from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import timedelta

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import ProcessingJob, RateLimitCounter, WorkerHeartbeat, utcnow
from app.services.jobs import claim_next_job, execute_job, recover_stale_jobs, run_maintenance
from scripts.run_worker import run_once


def _zip_payload() -> bytes:
    buffer = io.BytesIO()
    valid = {
        "document_type": "order",
        "number": "ASYNC-BATCH-1",
        "supplier_name": "Batch Supplier",
        "lines": [{"sku": "B-1", "quantity": 1, "unit_price": 5}],
    }
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("valid.json", json.dumps(valid))
        archive.writestr("notes.txt", "unsupported")
        archive.writestr("../unsafe.json", json.dumps(valid))
        archive.writestr("broken.json", "{not-json")
    return buffer.getvalue()


def test_async_batch_processes_supported_and_rejects_unsafe_members(client, auth):
    queued = client.post(
        "/api/jobs/batches",
        headers={**auth, "Idempotency-Key": "batch-extended-1"},
        files={"file": ("batch.zip", _zip_payload(), "application/zip")},
    )
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["job"]["id"]
    assert run_once("pytest-batch-worker") is True
    completed = client.get(f"/api/jobs/{job_id}", headers=auth).json()
    assert completed["status"] == "completed"
    outcomes = {item["filename"]: item["outcome"] for item in completed["result"]["results"]}
    assert outcomes["valid.json"] in {"ingested", "parse_failed"}
    assert outcomes["notes.txt"] == "skipped"
    assert outcomes["../unsafe.json"] == "rejected"
    assert outcomes["broken.json"] in {"parse_failed", "failed"}


def test_reanalysis_job_and_cancelled_job_paths(client, auth):
    reanalysis = client.post(
        "/api/jobs/reanalyze",
        headers={**auth, "Idempotency-Key": "reanalyze-extended"},
    )
    assert reanalysis.status_code == 202
    assert run_once("pytest-reanalysis-worker") is True
    completed = client.get(f"/api/jobs/{reanalysis.json()['job']['id']}", headers=auth).json()
    assert completed["status"] == "completed"
    assert completed["result"]["reanalyzed_chains"] == 0

    payload = {
        "document_type": "order",
        "number": "CANCEL-1",
        "lines": [{"sku": "C-1", "quantity": 1, "unit_price": 1}],
    }
    queued = client.post(
        "/api/jobs/documents",
        headers=auth,
        files={"file": ("cancel.json", json.dumps(payload).encode(), "application/json")},
    )
    job_id = queued.json()["job"]["id"]
    cancelled = client.delete(f"/api/jobs/{job_id}", headers=auth)
    assert cancelled.status_code == 200
    assert cancelled.json()["job"]["status"] == "cancelled"


def test_failed_job_is_retried_then_moved_to_terminal_failure(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    with SessionLocal() as db:
        job = ProcessingJob(
            tenant_id=me["tenant_id"],
            created_by=me["id"],
            job_type="reprocess_document",
            input_json=json.dumps({"document_id": "missing-document", "overrides": {}}),
            max_attempts=2,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    with SessionLocal() as db:
        job = claim_next_job(db, "failure-worker")
        assert job and job.id == job_id
        db.commit()
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        execute_job(db, job)
        db.commit()
        assert job.status == "queued"
        job.available_at = utcnow() - timedelta(seconds=1)
        db.commit()

    with SessionLocal() as db:
        job = claim_next_job(db, "failure-worker")
        assert job and job.id == job_id
        db.commit()
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        execute_job(db, job)
        db.commit()
        assert job.status == "failed"
        assert "Documento da rielaborare non trovato" in job.error_message


def test_stale_lease_recovery_and_maintenance_cleanup(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    old = utcnow() - timedelta(days=40)
    quarantine_file = settings.quarantine_dir / "orphan.json"
    quarantine_file.write_text("{}", encoding="utf-8")
    os.utime(quarantine_file, (old.timestamp(), old.timestamp()))

    with SessionLocal() as db:
        stale = ProcessingJob(
            tenant_id=me["tenant_id"],
            created_by=me["id"],
            job_type="reanalyze_tenant",
            status="running",
            attempts=1,
            max_attempts=3,
            locked_at=utcnow() - timedelta(seconds=settings.worker_lease_seconds + 10),
            locked_by="dead-worker",
        )
        completed = ProcessingJob(
            tenant_id=me["tenant_id"],
            created_by=me["id"],
            job_type="reanalyze_tenant",
            status="completed",
            completed_at=old,
        )
        db.add_all(
            [
                stale,
                completed,
                WorkerHeartbeat(worker_id="old-worker", hostname="host", last_seen_at=old),
                RateLimitCounter(key="old-limit", window_started_at=old, expires_at=old, count=99),
            ]
        )
        db.commit()
        assert recover_stale_jobs(db) == 1
        assert stale.status == "queued"
        metrics = run_maintenance(db)
        db.commit()
        assert metrics["deleted_jobs"] >= 1
        assert metrics["deleted_heartbeats"] >= 1
        assert metrics["deleted_rate_limits"] >= 1
        assert metrics["removed_quarantine"] >= 1
        assert db.scalar(select(ProcessingJob).where(ProcessingJob.id == completed.id)) is None
