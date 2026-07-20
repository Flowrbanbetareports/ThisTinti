def test_register_login_and_me(client):
    registration = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Alpha",
            "email": "owner@alpha.com",
            "password": "LongPassword123!",
        },
    )
    assert registration.status_code == 201
    token = registration.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["organization"] == "Alpha"

    login = client.post("/api/auth/login", json={"email": "owner@alpha.com", "password": "LongPassword123!"})
    assert login.status_code == 200


def test_duplicate_email_rejected(client):
    payload = {"organization_name": "Alpha", "email": "same@example.com", "password": "LongPassword123!"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    payload["organization_name"] = "Beta"
    assert client.post("/api/auth/register", json=payload).status_code == 409
