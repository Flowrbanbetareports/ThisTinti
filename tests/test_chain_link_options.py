import json


def upload(client, auth, filename, payload):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )


def test_link_options_explain_candidates_and_support_supervised_correction(client, auth):
    order = upload(
        client,
        auth,
        "order.json",
        {
            "document_type": "order",
            "number": "LINK-100",
            "supplier_name": "Link Supplier",
            "lines": [{"sku": "A", "quantity": 2, "unit_price": 10, "line_total": 20}],
        },
    ).json()["document"]
    invoice = upload(
        client,
        auth,
        "invoice.json",
        {
            "document_type": "invoice",
            "number": "INV-LINK-100",
            "supplier_name": "Link Supplier",
            "references": {"order_numbers": ["LINK-100"]},
            "lines": [{"sku": "A", "quantity": 2, "unit_price": 10, "line_total": 20}],
        },
    ).json()["document"]

    chains = client.get("/api/chains", headers=auth).json()
    chain = next(item for item in chains if order["id"] in item["documents"].get("order", []))
    assert invoice["id"] in chain["documents"].get("invoice", [])

    detached = client.delete(f"/api/chains/{chain['id']}/documents/{invoice['id']}", headers=auth)
    assert detached.status_code == 200

    options_response = client.get(f"/api/chains/{chain['id']}/link-options", headers=auth)
    assert options_response.status_code == 200
    options = options_response.json()
    linked_order = next(item for item in options["linked"] if item["document_id"] == order["id"])
    assert linked_order["role"] == "order"
    assert linked_order["match_reason"] in {"new_chain", "manual"}

    proposed_invoice = next(item for item in options["candidates"] if item["document_id"] == invoice["id"])
    assert proposed_invoice["role"] == "invoice"
    assert proposed_invoice["reason"] == "explicit_reference"
    assert proposed_invoice["confidence"] == 1.0
    assert proposed_invoice["supplier"] == "Link Supplier"

    attached = client.post(
        f"/api/chains/{chain['id']}/attach",
        headers=auth,
        json={"document_id": invoice["id"], "role": "invoice"},
    )
    assert attached.status_code == 200

    updated = client.get(f"/api/chains/{chain['id']}/link-options", headers=auth).json()
    linked_invoice = next(item for item in updated["linked"] if item["document_id"] == invoice["id"])
    assert linked_invoice["match_reason"] == "manual"
    assert linked_invoice["match_confidence"] == 1.0
    assert all(item["document_id"] != invoice["id"] for item in updated["candidates"])


def test_link_options_are_tenant_scoped_and_validate_chain(client, auth):
    assert client.get("/api/chains/missing/link-options", headers=auth).status_code == 404
