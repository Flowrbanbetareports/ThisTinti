import json


def _upload(client, auth, name: str, payload: dict):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (name, json.dumps(payload).encode(), "application/json")},
    )


def test_high_confidence_description_similarity_links_documents(client, auth):
    order = {
        "document_type": "order",
        "number": "FUZZY-1",
        "document_date": "2026-07-01",
        "supplier_name": "Fuzzy Supplier",
        "lines": [{"description": "Giacca classica uomo blu", "quantity": 10, "unit_price": 25}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-FUZZY",
        "document_date": "2026-07-03",
        "supplier_name": "Fuzzy Supplier",
        "lines": [{"description": "Giacca classica uomo blu navy", "quantity": 10, "unit_price": 25}],
    }
    assert _upload(client, auth, "order-fuzzy.json", order).status_code == 201
    assert _upload(client, auth, "invoice-fuzzy.json", invoice).status_code == 201
    chains = client.get("/api/chains", headers=auth).json()
    assert len(chains) == 1
    assert len(chains[0]["documents"]["order"]) == 1
    assert len(chains[0]["documents"]["invoice"]) == 1


def test_low_similarity_does_not_silently_link(client, auth):
    order = {
        "document_type": "order",
        "number": "DISTINCT-1",
        "document_date": "2026-07-01",
        "supplier_name": "Distinct Supplier",
        "lines": [{"description": "Giacca classica uomo blu", "quantity": 10, "unit_price": 25}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-DISTINCT",
        "document_date": "2026-07-03",
        "supplier_name": "Distinct Supplier",
        "lines": [{"description": "Scarpa running donna rossa", "quantity": 10, "unit_price": 25}],
    }
    assert _upload(client, auth, "order-distinct.json", order).status_code == 201
    assert _upload(client, auth, "invoice-distinct.json", invoice).status_code == 201
    assert len(client.get("/api/chains", headers=auth).json()) == 2


def test_reprocess_rebuilds_chain_role(client, auth):
    payload = {
        "document_type": "invoice",
        "number": "ROLE-1",
        "supplier_name": "Role Supplier",
        "lines": [{"sku": "A", "quantity": 2, "unit_price": 4}],
    }
    uploaded = _upload(client, auth, "role.json", payload)
    document_id = uploaded.json()["document"]["id"]
    before = client.get("/api/chains", headers=auth).json()
    assert before[0]["documents"]["invoice"] == [document_id]

    corrected = client.post(
        f"/api/documents/{document_id}/reprocess",
        headers=auth,
        json={"document_type": "order", "number": "ROLE-1", "supplier_name": "Role Supplier"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["document_type"] == "order"
    chains = client.get("/api/chains", headers=auth).json()
    assert any(document_id in chain["documents"].get("order", []) for chain in chains)
    assert not any(document_id in chain["documents"].get("invoice", []) for chain in chains)


def test_manual_attach_detach_and_conflict_guard(client, auth):
    one = {
        "document_type": "order",
        "number": "CHAIN-A",
        "supplier_name": "Manual Supplier",
        "lines": [{"sku": "A", "quantity": 1, "unit_price": 1}],
    }
    two = {
        "document_type": "order",
        "number": "CHAIN-B",
        "supplier_name": "Manual Supplier",
        "lines": [{"sku": "B", "quantity": 1, "unit_price": 1}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-MANUAL",
        "supplier_name": "Manual Supplier",
        "lines": [{"sku": "C", "quantity": 1, "unit_price": 1}],
    }
    doc_a = _upload(client, auth, "a.json", one).json()["document"]["id"]
    doc_b = _upload(client, auth, "b.json", two).json()["document"]["id"]
    invoice_id = _upload(client, auth, "manual-invoice.json", invoice).json()["document"]["id"]
    chains = client.get("/api/chains", headers=auth).json()
    chain_a = next(c for c in chains if doc_a in c["documents"].get("order", []))
    chain_b = next(c for c in chains if doc_b in c["documents"].get("order", []))
    invoice_chain = next(c for c in chains if invoice_id in c["documents"].get("invoice", []))

    assert client.delete(f"/api/chains/{invoice_chain['id']}/documents/{invoice_id}", headers=auth).status_code == 200
    assert (
        client.post(
            f"/api/chains/{chain_a['id']}/attach",
            headers=auth,
            json={"document_id": invoice_id, "role": "invoice"},
        ).status_code
        == 200
    )
    conflict = client.post(
        f"/api/chains/{chain_b['id']}/attach",
        headers=auth,
        json={"document_id": invoice_id, "role": "invoice"},
    )
    assert conflict.status_code == 409
