def test_browser_cookie_session_requires_csrf_for_mutations(client):
    registered = client.post(
        "/api/auth/register",
        json={
            "organization_name": "Cookie Company",
            "email": "cookie@example.com",
            "password": "CookiePassword123!",
        },
    )
    assert registered.status_code == 201
    assert "token" not in registered.json()
    set_cookie = registered.headers.get_list("set-cookie")
    assert any(
        "thistinti_session=" in value and "HttpOnly" in value and "SameSite=strict" in value for value in set_cookie
    )
    assert any("thistinti_csrf=" in value and "SameSite=strict" in value for value in set_cookie)
    assert client.get("/api/auth/me").status_code == 200

    blocked = client.post("/api/demo/load")
    assert blocked.status_code == 403
    csrf = client.cookies.get("thistinti_csrf")
    allowed = client.post("/api/demo/load", headers={"X-CSRF-Token": csrf})
    assert allowed.status_code == 200

    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_explicit_token_mode_remains_available_for_integrations(client):
    registered = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "API Company",
            "email": "api@example.com",
            "password": "ApiPassword123!",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["token"]


def test_cross_origin_mutation_is_rejected(client):
    response = client.post(
        "/api/auth/register",
        headers={"Origin": "https://attacker.invalid"},
        json={
            "organization_name": "Blocked",
            "email": "blocked@example.com",
            "password": "BlockedPassword123!",
        },
    )
    assert response.status_code == 403
