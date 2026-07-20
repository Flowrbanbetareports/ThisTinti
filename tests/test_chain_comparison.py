import json


def upload(client, auth, filename, payload):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )


def test_chain_detail_returns_row_by_row_comparison(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-COMP-1",
        "supplier_name": "Comparison Supplier",
        "lines": [{"sku": "A-100", "description": "Item A", "quantity": 10, "unit_price": 20, "discount_rate": 5}],
    }
    delivery = {
        "document_type": "delivery",
        "number": "DDT-COMP-1",
        "supplier_name": "Comparison Supplier",
        "references": {"order_numbers": ["PO-COMP-1"]},
        "lines": [{"sku": "A100", "description": "Item A", "quantity": 8, "unit_price": 20, "discount_rate": 5}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-COMP-1",
        "supplier_name": "Comparison Supplier",
        "references": {"order_numbers": ["PO-COMP-1"]},
        "lines": [{"sku": "A-100", "description": "Item A", "quantity": 10, "unit_price": 22, "discount_rate": 0}],
    }
    for name, payload in (("order.json", order), ("delivery.json", delivery), ("invoice.json", invoice)):
        assert upload(client, auth, name, payload).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    response = client.get(f"/api/chains/{chain_id}", headers=auth)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["comparison"]["summary"]["row_count"] == 1
    row = detail["comparison"]["rows"][0]
    assert row["values"]["order"]["quantity"] == 10
    assert row["values"]["delivery"]["quantity"] == 8
    assert row["values"]["invoice"]["unit_price"] == 22
    assert row["status"] == "issue"
    assert "quantità fatturata superiore" in row["reasons"]
    assert "prezzo superiore" in row["reasons"]
    assert detail["cases"]


def test_chain_detail_is_tenant_isolated(client, auth):
    payload = {
        "document_type": "order",
        "number": "PO-PRIVATE",
        "supplier_name": "Private Supplier",
        "lines": [{"sku": "P", "quantity": 1, "unit_price": 1}],
    }
    assert upload(client, auth, "private.json", payload).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    other = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Other Chain Tenant",
            "email": "other-chain@example.com",
            "password": "SecurePass456!",
        },
    )
    other_auth = {"Authorization": f"Bearer {other.json()['token']}"}
    assert client.get(f"/api/chains/{chain_id}", headers=other_auth).status_code == 404
