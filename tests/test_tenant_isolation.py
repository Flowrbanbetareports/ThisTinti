from pathlib import Path

SAMPLE = Path(__file__).parents[1] / "samples" / "order.json"


def register(client, org, email):
    r = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={"organization_name": org, "email": email, "password": "SecurePass123!"},
    )
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_documents_are_tenant_isolated(client):
    a = register(client, "Alpha", "a@example.com")
    b = register(client, "Beta", "b@example.com")
    with SAMPLE.open("rb") as handle:
        assert (
            client.post(
                "/api/documents/upload", headers=a, files={"file": ("order.json", handle, "application/json")}
            ).status_code
            == 201
        )
    assert len(client.get("/api/documents", headers=a).json()) == 1
    assert client.get("/api/documents", headers=b).json() == []
