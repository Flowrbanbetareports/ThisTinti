import json
from pathlib import Path


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login", headers={"X-Session-Mode": "token"}, json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_disabled_user_cannot_login_and_old_token_is_revoked(client, auth):
    created = client.post(
        "/api/users",
        headers=auth,
        json={"email": "disabled@example.com", "password": "DisabledPass123!", "role": "viewer"},
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    viewer = _login(client, "disabled@example.com", "DisabledPass123!")
    assert client.get("/api/dashboard", headers=viewer).status_code == 200

    disabled = client.patch(f"/api/users/{user_id}/status", headers=auth, json={"active": False})
    assert disabled.status_code == 200
    assert client.get("/api/dashboard", headers=viewer).status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "disabled@example.com", "password": "DisabledPass123!"},
        ).status_code
        == 401
    )


def test_password_reset_and_role_change_revoke_existing_tokens(client, auth):
    created = client.post(
        "/api/users",
        headers=auth,
        json={"email": "member@example.com", "password": "MemberPass123!", "role": "viewer"},
    )
    user_id = created.json()["id"]
    old_token = _login(client, "member@example.com", "MemberPass123!")

    reset = client.post(
        f"/api/users/{user_id}/reset-password",
        headers=auth,
        json={"new_password": "MemberPass456!"},
    )
    assert reset.status_code == 200
    assert client.get("/api/dashboard", headers=old_token).status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "MemberPass123!"},
        ).status_code
        == 401
    )

    viewer = _login(client, "member@example.com", "MemberPass456!")
    changed = client.patch(f"/api/users/{user_id}/role", headers=auth, json={"role": "reviewer"})
    assert changed.status_code == 200
    assert client.get("/api/dashboard", headers=viewer).status_code == 401
    reviewer = _login(client, "member@example.com", "MemberPass456!")
    assert client.get("/api/auth/me", headers=reviewer).json()["role"] == "reviewer"


def test_last_administrator_cannot_be_disabled_or_demoted(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    assert client.patch(f"/api/users/{me['id']}/status", headers=auth, json={"active": False}).status_code == 422
    assert client.patch(f"/api/users/{me['id']}/role", headers=auth, json={"role": "viewer"}).status_code == 422


def test_upload_rejects_empty_and_unsupported_files(client, auth):
    unsupported = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert unsupported.status_code == 415

    empty = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("empty.json", b"", "application/json")},
    )
    assert empty.status_code == 422


def test_uploaded_filename_is_reduced_to_basename(client, auth):
    payload = {
        "document_type": "order",
        "number": "SAFE-1",
        "supplier_name": "Safe Supplier",
        "lines": [{"sku": "A", "quantity": 1, "unit_price": 1}],
    }
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("../../unsafe name.json", json.dumps(payload).encode(), "application/json")},
    )
    assert response.status_code == 201
    document = response.json()["document"]
    assert document["source_filename"] == "unsafe name.json"
    downloaded = client.get(f"/api/documents/{document['id']}/file", headers=auth)
    assert downloaded.status_code == 200


def test_login_rate_limit_returns_429(client):
    for _ in range(12):
        response = client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "IncorrectPassword123!"},
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "IncorrectPassword123!"},
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"


def test_reprocess_preserves_last_good_lines_after_failure(client, auth):
    sample = Path(__file__).parents[1] / "samples" / "order.json"
    with sample.open("rb") as handle:
        uploaded = client.post(
            "/api/documents/upload",
            headers=auth,
            files={"file": ("order.json", handle, "application/json")},
        )
    document = uploaded.json()["document"]
    assert len(document["lines"]) > 0

    # Corrupt the stored file through the test database to exercise the safe failure path.
    from app.db import SessionLocal
    from app.models import Document

    with SessionLocal() as db:
        stored = db.get(Document, document["id"])
        Path(stored.storage_path).write_text("{broken", encoding="utf-8")

    failed = client.post(
        f"/api/documents/{document['id']}/reprocess",
        headers=auth,
        json={"document_type": "order"},
    )
    assert failed.status_code == 422
    current = client.get(f"/api/documents/{document['id']}", headers=auth).json()
    assert current["parse_status"] == "parsed"
    assert len(current["lines"]) == len(document["lines"])
    assert "Rielaborazione non applicata" in current["parse_message"]


def test_frontend_core_remains_auditable_with_a_bounded_experience_layer():
    static = Path(__file__).parents[1] / "app" / "static"
    loader = (static / "app.js").read_text(encoding="utf-8")
    core = (static / "app-core.js").read_text(encoding="utf-8")
    experience = (static / "onboarding.js").read_text(encoding="utf-8")

    assert not (static / "app-original.js").exists()
    assert not (static / "app-fixes.js").exists()
    assert "messageFrom" in core
    assert "[object Object]" not in core
    assert "function dateTime" in core
    assert "`${raw}Z`" in core
    assert "'/app-core.js'" in loader
    assert "'/onboarding.js'" in loader
    assert loader.index("'/app-core.js'") < loader.index("'/onboarding.js'")
    assert "fetch(" not in experience
    assert "/api/" not in experience
