from __future__ import annotations

import json


def test_api_credential_can_ingest_and_is_immediately_revocable(client, auth):
    created = client.post(
        "/api/api-credentials",
        headers=auth,
        json={"name": "ERP connector", "role": "reviewer", "scopes": ["read", "ingest"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    token = body["token"]
    api_auth = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=api_auth)
    assert me.status_code == 200
    assert me.json()["principal_type"] == "api_credential"

    payload = {
        "document_type": "order",
        "number": "API-PO-1",
        "supplier_name": "API Supplier",
        "lines": [{"sku": "API-1", "quantity": 1, "unit_price": 5}],
    }
    queued = client.post(
        "/api/jobs/documents",
        headers={**api_auth, "Idempotency-Key": "api-credential-upload-1"},
        files={"file": ("api-order.json", json.dumps(payload).encode(), "application/json")},
    )
    assert queued.status_code == 202, queued.text

    revoked = client.delete(f"/api/api-credentials/{body['id']}", headers=auth)
    assert revoked.status_code == 200
    assert client.get("/api/auth/me", headers=api_auth).status_code == 401


def test_api_credential_scopes_are_enforced(client, auth):
    created = client.post(
        "/api/api-credentials",
        headers=auth,
        json={"name": "Read only BI", "role": "viewer", "scopes": ["read"]},
    )
    assert created.status_code == 201
    api_auth = {"Authorization": f"Bearer {created.json()['token']}"}
    assert client.get("/api/documents", headers=api_auth).status_code == 200
    denied = client.post(
        "/api/jobs/reanalyze",
        headers=api_auth,
    )
    assert denied.status_code == 403


def test_api_secret_is_not_returned_by_listing(client, auth):
    created = client.post(
        "/api/api-credentials",
        headers=auth,
        json={"name": "One time secret", "role": "viewer", "scopes": ["read"]},
    ).json()
    listing = client.get("/api/api-credentials", headers=auth)
    assert listing.status_code == 200
    item = next(item for item in listing.json() if item["id"] == created["id"])
    assert "token" not in item
    assert item["key_prefix"]
