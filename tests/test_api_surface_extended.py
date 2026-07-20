from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db import SessionLocal
from app.models import Document, DocumentLine, WorkerHeartbeat
from scripts.run_worker import run_once


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        headers={"X-Session-Mode": "token"},
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_identity_admin_and_worker_management_surface(client, auth):
    sessions = client.get("/api/auth/sessions", headers=auth)
    assert sessions.status_code == 200
    assert any(item["current"] for item in sessions.json())
    assert client.delete("/api/auth/sessions/missing", headers=auth).status_code == 404

    second = _login(client, "admin@example.com", "SecurePass123!")
    second_id = next(
        item["id"] for item in client.get("/api/auth/sessions", headers=auth).json() if not item["current"]
    )
    revoked = client.delete(f"/api/auth/sessions/{second_id}", headers=auth)
    assert revoked.status_code == 200
    assert client.get("/api/auth/me", headers=second).status_code == 401

    assert (
        client.post(
            "/api/api-credentials",
            headers=auth,
            json={"name": "bad viewer", "role": "viewer", "scopes": ["read", "ingest"]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/api-credentials",
            headers=auth,
            json={"name": "empty reviewer", "role": "reviewer", "scopes": []},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/api-credentials",
            headers=auth,
            json={
                "name": "expired key",
                "role": "viewer",
                "scopes": ["read"],
                "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            },
        ).status_code
        == 422
    )
    created_key = client.post(
        "/api/api-credentials",
        headers=auth,
        json={"name": "reporting key", "role": "viewer", "scopes": ["read"]},
    )
    assert created_key.status_code == 201
    key_payload = created_key.json()
    machine_auth = {"Authorization": f"Bearer {key_payload['token']}"}
    assert client.get("/api/auth/me", headers=machine_auth).json()["principal_type"] == "api_credential"
    assert client.post("/api/auth/logout", headers=machine_auth).status_code == 422
    assert len(client.get("/api/api-credentials", headers=auth).json()) == 1
    assert client.delete("/api/api-credentials/missing", headers=auth).status_code == 404
    assert client.delete(f"/api/api-credentials/{key_payload['id']}", headers=auth).status_code == 200
    assert client.get("/api/auth/me", headers=machine_auth).status_code == 401

    assert client.get("/api/users", headers=auth).status_code == 200
    created_user = client.post(
        "/api/users",
        headers=auth,
        json={"email": "surface@example.com", "password": "SurfacePass123!", "role": "reviewer"},
    )
    assert created_user.status_code == 201
    user_id = created_user.json()["id"]
    assert (
        client.post(
            "/api/users",
            headers=auth,
            json={"email": "surface@example.com", "password": "SurfacePass123!", "role": "viewer"},
        ).status_code
        == 409
    )
    assert client.patch("/api/users/missing/status", headers=auth, json={"active": False}).status_code == 404
    assert client.patch("/api/users/missing/role", headers=auth, json={"role": "viewer"}).status_code == 404
    assert (
        client.post(
            "/api/users/missing/reset-password", headers=auth, json={"new_password": "NewPass12345!"}
        ).status_code
        == 404
    )
    assert client.patch(f"/api/users/{user_id}/role", headers=auth, json={"role": "viewer"}).status_code == 200
    assert client.patch(f"/api/users/{user_id}/status", headers=auth, json={"active": False}).status_code == 200
    assert (
        client.post(
            f"/api/users/{user_id}/reset-password", headers=auth, json={"new_password": "NewPass12345!"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/change-password",
            headers=auth,
            json={"current_password": "wrong-password", "new_password": "AnotherPass123!"},
        ).status_code
        == 401
    )

    assert client.get("/api/system/workers", headers=auth).json() == []
    run_once("surface-worker")
    workers = client.get("/api/system/workers", headers=auth)
    assert workers.status_code == 200
    assert workers.json()[0]["worker_id"] == "surface-worker"
    with SessionLocal() as db:
        heartbeat = db.get(WorkerHeartbeat, "surface-worker")
        heartbeat.last_seen_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    assert client.get("/api/system/workers", headers=auth).json()[0]["stale"] is True


def test_operational_document_chain_case_and_export_surface(client, auth):
    loaded = client.post("/api/demo/load", headers=auth)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["loaded"] == 4

    dashboard = client.get("/api/dashboard", headers=auth)
    assert dashboard.status_code == 200
    documents = client.get("/api/documents?parse_status=parsed&limit=10&offset=0", headers=auth).json()
    assert len(documents) == 4
    assert client.get("/api/documents?document_type=order", headers=auth).status_code == 200
    document = documents[0]
    detail = client.get(f"/api/documents/{document['id']}", headers=auth)
    assert detail.status_code == 200
    assert "lines" in detail.json()
    assert client.get("/api/documents/missing", headers=auth).status_code == 404
    assert client.get("/api/documents/missing/file", headers=auth).status_code == 404
    assert client.post("/api/documents/missing/archive", headers=auth).status_code == 404
    assert client.post("/api/documents/missing/reprocess", headers=auth, json={}).status_code == 404

    file_response = client.get(f"/api/documents/{document['id']}/file", headers=auth)
    assert file_response.status_code == 200
    with SessionLocal() as db:
        stored = db.get(Document, document["id"])
        original_path = Path(stored.storage_path)
        moved_path = original_path.with_suffix(original_path.suffix + ".missing")
        original_path.rename(moved_path)
    try:
        assert client.get(f"/api/documents/{document['id']}/file", headers=auth).status_code == 410
    finally:
        moved_path.rename(original_path)

    chains = client.get("/api/chains?limit=50&offset=0", headers=auth)
    assert chains.status_code == 200
    chain = chains.json()[0]
    chain_id = chain["id"]
    chain_detail = client.get(f"/api/chains/{chain_id}", headers=auth)
    assert chain_detail.status_code == 200
    assert client.get("/api/chains/missing", headers=auth).status_code == 404
    assert client.post("/api/chains/missing/analyze", headers=auth).status_code == 404
    assert (
        client.post(
            f"/api/chains/{chain_id}/attach",
            headers=auth,
            json={"document_id": document["id"], "role": "not-the-type"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/chains/missing/attach",
            headers=auth,
            json={"document_id": document["id"], "role": document["document_type"]},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/chains/{chain_id}/documents/missing", headers=auth).status_code == 404
    assert client.post(f"/api/chains/{chain_id}/analyze", headers=auth).status_code == 200

    cases = client.get("/api/cases?limit=50&offset=0", headers=auth).json()
    assert cases
    case = cases[0]
    assert client.get(f"/api/cases/{case['id']}", headers=auth).status_code == 200
    assert client.get("/api/cases/missing", headers=auth).status_code == 404
    assert client.post("/api/cases/missing/decision", headers=auth, json={"decision": "confirmed"}).status_code == 404
    decided = client.post(
        f"/api/cases/{case['id']}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "verified in API surface test"},
    )
    assert decided.status_code == 200
    assert client.get("/api/cases?status=confirmed", headers=auth).status_code == 200
    assert client.get(f"/api/cases?severity={case['severity']}", headers=auth).status_code == 200

    assert client.get("/api/audit?limit=50&offset=0", headers=auth).status_code == 200
    assert client.get("/api/audit/verify", headers=auth).json()["valid"] is True

    export = client.get("/api/export?include_files=true", headers=auth)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/zip")
    assert export.content.startswith(b"PK")

    archived = client.post(f"/api/documents/{document['id']}/archive", headers=auth)
    assert archived.status_code == 200
    assert document["id"] not in {item["id"] for item in client.get("/api/documents", headers=auth).json()}


def test_validation_discovery_and_alias_error_surface(client, auth):
    assert client.get("/api/validation/datasets", headers=auth).json() == []
    loaded = client.post("/api/validation/load-default", headers=auth)
    assert loaded.status_code == 201
    dataset_id = loaded.json()["id"]
    duplicate_load = client.post("/api/validation/load-default", headers=auth)
    assert duplicate_load.status_code == 201
    assert duplicate_load.json()["id"] == dataset_id
    assert client.get(f"/api/validation/datasets/{dataset_id}", headers=auth).status_code == 200
    assert client.get("/api/validation/datasets/missing", headers=auth).status_code == 404
    assert (
        client.patch("/api/validation/datasets/missing/status", headers=auth, json={"status": "archived"}).status_code
        == 404
    )
    assert client.post("/api/validation/datasets/missing/run", headers=auth).status_code == 404

    run = client.post(f"/api/validation/datasets/{dataset_id}/run", headers=auth)
    assert run.status_code == 201
    run_id = run.json()["id"]
    assert client.get(f"/api/validation/runs/{run_id}", headers=auth).status_code == 200
    assert client.get("/api/validation/runs/missing", headers=auth).status_code == 404
    assert len(client.get(f"/api/validation/runs?dataset_id={dataset_id}", headers=auth).json()) == 1
    assert (
        client.patch(
            f"/api/validation/datasets/{dataset_id}/status", headers=auth, json={"status": "archived"}
        ).status_code
        == 200
    )
    assert client.post(f"/api/validation/datasets/{dataset_id}/run", headers=auth).status_code == 404
    assert len(client.get("/api/validation/datasets?include_archived=true", headers=auth).json()) == 1

    no_profile = client.post("/api/discovery/profile/decision", headers=auth, json={"decision": "confirmed"})
    assert no_profile.status_code == 404
    invalid_thresholds = client.post(
        "/api/discovery/run",
        headers=auth,
        json={"minimum_documents": 1, "auto_activate_threshold": 0.7, "confirmation_threshold": 0.8},
    )
    assert invalid_thresholds.status_code == 422
    discovery = client.post(
        "/api/discovery/run",
        headers=auth,
        json={"minimum_documents": 1, "auto_activate_threshold": 0.92, "confirmation_threshold": 0.68},
    )
    assert discovery.status_code == 201
    assert client.get("/api/discovery/profile", headers=auth).status_code == 200
    assert client.get("/api/discovery/runs", headers=auth).status_code == 200
    assert client.get("/api/discovery/rules?status=needs_confirmation", headers=auth).status_code == 200
    assert (
        client.post("/api/discovery/rules/missing/decision", headers=auth, json={"decision": "rejected"}).status_code
        == 404
    )
    assert (
        client.post(
            "/api/discovery/profile/decision",
            headers=auth,
            json={"decision": "corrected"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/discovery/profile/decision",
            headers=auth,
            json={"decision": "corrected", "activity_type": "custom", "activity_label": "Custom activity"},
        ).status_code
        == 200
    )
    assert client.post("/api/discovery/profile/decision", headers=auth, json={"decision": "relearn"}).status_code == 200

    assert client.get("/api/item-aliases", headers=auth).json() == []
    assert (
        client.post(
            "/api/item-aliases/confirm",
            headers=auth,
            json={"canonical_line_id": "missing", "alias_line_id": "also-missing"},
        ).status_code
        == 404
    )
    client.post("/api/demo/load", headers=auth)
    with SessionLocal() as db:
        line = db.query(DocumentLine).first()
        line_id = line.id
    assert (
        client.post(
            "/api/item-aliases/confirm",
            headers=auth,
            json={"canonical_line_id": line_id, "alias_line_id": line_id},
        ).status_code
        == 422
    )
