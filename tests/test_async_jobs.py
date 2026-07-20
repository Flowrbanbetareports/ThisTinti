from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.parsers import ParseError
from app.services.file_security import scan_file
from scripts.run_worker import run_once


def test_async_document_job_is_persistent_and_processed(client, auth):
    payload = {
        "document_type": "order",
        "number": "ASYNC-PO-1",
        "supplier_name": "Async Supplier",
        "lines": [{"sku": "ASYNC-1", "quantity": 2, "unit_price": 15}],
    }
    queued = client.post(
        "/api/jobs/documents",
        headers={**auth, "Idempotency-Key": "async-order-1"},
        files={"file": ("async-order.json", json.dumps(payload).encode(), "application/json")},
    )
    assert queued.status_code == 202, queued.text
    job = queued.json()["job"]
    assert job["status"] == "queued"
    assert run_once("pytest-worker") is True
    completed = client.get(f"/api/jobs/{job['id']}", headers=auth)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    document_id = completed.json()["result"]["document_id"]
    assert client.get(f"/api/documents/{document_id}", headers=auth).status_code == 200


def test_async_upload_idempotency_returns_original_job(client, auth):
    payload = {
        "document_type": "order",
        "number": "ASYNC-IDEMPOTENT",
        "supplier_name": "Async Supplier",
        "lines": [{"sku": "I-1", "quantity": 1, "unit_price": 1}],
    }
    headers = {**auth, "Idempotency-Key": "stable-key-1"}
    first = client.post(
        "/api/jobs/documents",
        headers=headers,
        files={"file": ("one.json", json.dumps(payload).encode(), "application/json")},
    )
    second = client.post(
        "/api/jobs/documents",
        headers=headers,
        files={"file": ("two.json", json.dumps(payload).encode(), "application/json")},
    )
    assert first.status_code == second.status_code == 202
    assert first.json()["job"]["id"] == second.json()["job"]["id"]
    assert second.json()["created"] is False


def test_structural_malware_scan_rejects_eicar(tmp_path: Path):
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"%PDF-1.4\nX5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE")
    with pytest.raises(ParseError, match="malware"):
        scan_file(path)


def test_async_reprocess_job_updates_document(client, auth):
    original = {
        "document_type": "order",
        "number": "ASYNC-REPROCESS-1",
        "supplier_name": "Async Supplier",
        "lines": [{"sku": "R-1", "quantity": 1, "unit_price": 12}],
    }
    uploaded = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("reprocess.json", json.dumps(original).encode(), "application/json")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["document"]["id"]
    queued = client.post(
        f"/api/jobs/documents/{document_id}/reprocess",
        headers={**auth, "Idempotency-Key": "reprocess-once"},
        json={"number": "ASYNC-REPROCESS-UPDATED"},
    )
    assert queued.status_code == 202, queued.text
    assert run_once("pytest-reprocess-worker") is True
    completed = client.get(f"/api/jobs/{queued.json()['job']['id']}", headers=auth).json()
    assert completed["status"] == "completed"
    document = client.get(f"/api/documents/{document_id}", headers=auth).json()
    assert document["number"] == "ASYNC-REPROCESS-UPDATED"


def test_synchronous_ingestion_can_be_disabled(client, auth):
    from app.config import settings

    original = settings.allow_synchronous_ingestion
    object.__setattr__(settings, "allow_synchronous_ingestion", False)
    try:
        response = client.post(
            "/api/documents/upload",
            headers=auth,
            files={"file": ("blocked.json", b"{}", "application/json")},
        )
        assert response.status_code == 409
    finally:
        object.__setattr__(settings, "allow_synchronous_ingestion", original)
