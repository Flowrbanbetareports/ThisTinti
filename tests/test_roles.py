from pathlib import Path


def _token(client, email, password):
    response = client.post(
        "/api/auth/login",
        headers={"X-Session-Mode": "token"},
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_admin_creates_viewer_and_permissions_are_enforced(client, auth):
    created = client.post(
        "/api/users",
        headers=auth,
        json={
            "email": "viewer@example.com",
            "password": "ViewerPassword123!",
            "role": "viewer",
        },
    )
    assert created.status_code == 201
    viewer = _token(client, "viewer@example.com", "ViewerPassword123!")
    assert client.get("/api/dashboard", headers=viewer).status_code == 200
    assert client.get("/api/documents", headers=viewer).status_code == 200
    assert client.get("/api/audit", headers=viewer).status_code == 403
    assert client.get("/api/export", headers=viewer).status_code == 403
    sample = Path(__file__).parents[1] / "samples" / "order.json"
    with sample.open("rb") as handle:
        upload = client.post(
            "/api/documents/upload", headers=viewer, files={"file": ("order.json", handle, "application/json")}
        )
    assert upload.status_code == 403


def test_reviewer_can_upload_and_review_but_not_manage_users(client, auth):
    response = client.post(
        "/api/users",
        headers=auth,
        json={
            "email": "reviewer@example.com",
            "password": "ReviewerPassword123!",
            "role": "reviewer",
        },
    )
    assert response.status_code == 201
    reviewer = _token(client, "reviewer@example.com", "ReviewerPassword123!")
    sample_dir = Path(__file__).parents[1] / "samples"
    for name in ("order.json", "delivery.json", "invoice.json"):
        with (sample_dir / name).open("rb") as handle:
            response = client.post(
                "/api/documents/upload", headers=reviewer, files={"file": (name, handle, "application/json")}
            )
        assert response.status_code == 201
    case_id = client.get("/api/cases", headers=reviewer).json()[0]["id"]
    assert (
        client.post(f"/api/cases/{case_id}/decision", headers=reviewer, json={"decision": "confirmed"}).status_code
        == 200
    )
    assert client.get("/api/users", headers=reviewer).status_code == 403


def test_password_change_and_self_disable_guard(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    blocked = client.patch(f"/api/users/{me['id']}/status", headers=auth, json={"active": False})
    assert blocked.status_code == 422
    changed = client.post(
        "/api/auth/change-password",
        headers=auth,
        json={
            "current_password": "SecurePass123!",
            "new_password": "NewSecurePass123!",
        },
    )
    assert changed.status_code == 200
    assert (
        client.post("/api/auth/login", json={"email": "admin@example.com", "password": "SecurePass123!"}).status_code
        == 401
    )
    assert (
        client.post("/api/auth/login", json={"email": "admin@example.com", "password": "NewSecurePass123!"}).status_code
        == 200
    )
