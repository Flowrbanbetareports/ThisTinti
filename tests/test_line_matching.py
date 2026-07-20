import json


def upload_payload(client, auth, filename, payload):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )


def active_case_types(client, auth):
    return {
        case["case_type"]
        for case in client.get("/api/cases", headers=auth).json()
        if case["status"] in {"open", "needs_review", "confirmed"}
    }


def test_explainable_fuzzy_matching_handles_supplier_code_variants(client, auth):
    supplier = "Variant Supplier"
    order = {
        "document_type": "order",
        "number": "PO-FUZZY-1",
        "supplier_name": supplier,
        "lines": [
            {
                "sku": "GIACCA-145",
                "description": "Giacca tecnica",
                "color": "Blu",
                "size": "48",
                "quantity": 10,
                "unit_price": 40,
                "discount_rate": 5,
            }
        ],
    }
    delivery = {
        "document_type": "delivery",
        "number": "DDT-FUZZY-1",
        "supplier_name": supplier,
        "references": {"order_numbers": ["PO-FUZZY-1"]},
        "lines": [
            {
                "sku": "ART.145",
                "description": "Giacca tecnica navy",
                "color": "Navy",
                "size": "EU48",
                "quantity": 8,
                "unit_price": 40,
                "discount_rate": 5,
            }
        ],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-FUZZY-1",
        "supplier_name": supplier,
        "references": {"order_numbers": ["PO-FUZZY-1"]},
        "lines": [
            {
                "sku": "145-GIACCA",
                "description": "Giacca tecnica blue",
                "color": "Blue",
                "size": "48",
                "quantity": 10,
                "unit_price": 42,
                "discount_rate": 0,
            }
        ],
    }
    for name, payload in (("order.json", order), ("delivery.json", delivery), ("invoice.json", invoice)):
        response = upload_payload(client, auth, name, payload)
        assert response.status_code == 201, response.text

    types = active_case_types(client, auth)
    assert "invoiced_over_received" in types
    assert "price_over_order" in types
    assert "discount_missing" in types
    assert "unmatched_invoice_line" not in types


def test_variant_conflict_blocks_fuzzy_merge(client, auth):
    supplier = "Size Conflict Supplier"
    order = {
        "document_type": "order",
        "number": "PO-SIZE-1",
        "supplier_name": supplier,
        "lines": [{"sku": "JACKET-100", "description": "Jacket", "size": "48", "quantity": 2, "unit_price": 30}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-SIZE-1",
        "supplier_name": supplier,
        "references": {"order_numbers": ["PO-SIZE-1"]},
        "lines": [{"sku": "JACKET100", "description": "Jacket", "size": "50", "quantity": 2, "unit_price": 35}],
    }
    assert upload_payload(client, auth, "order.json", order).status_code == 201
    assert upload_payload(client, auth, "invoice.json", invoice).status_code == 201
    types = active_case_types(client, auth)
    assert "unmatched_invoice_line" in types
    assert "price_over_order" not in types


def test_confirmed_alias_reanalyzes_existing_chain(client, auth):
    supplier = "Alias Learning Supplier"
    order = {
        "document_type": "order",
        "number": "PO-ALIAS-1",
        "supplier_name": supplier,
        "lines": [{"sku": "X-ALPHA", "description": "Alpha component", "quantity": 4, "unit_price": 10}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-ALIAS-1",
        "supplier_name": supplier,
        "references": {"order_numbers": ["PO-ALIAS-1"]},
        "lines": [{"sku": "Z-900", "description": "Supplier special code", "quantity": 4, "unit_price": 12}],
    }
    assert upload_payload(client, auth, "order.json", order).status_code == 201
    assert upload_payload(client, auth, "invoice.json", invoice).status_code == 201
    assert "unmatched_invoice_line" in active_case_types(client, auth)

    documents = client.get("/api/documents", headers=auth).json()
    order_id = next(doc["id"] for doc in documents if doc["document_type"] == "order")
    invoice_id = next(doc["id"] for doc in documents if doc["document_type"] == "invoice")
    order_line_id = client.get(f"/api/documents/{order_id}", headers=auth).json()["lines"][0]["id"]
    invoice_line_id = client.get(f"/api/documents/{invoice_id}", headers=auth).json()["lines"][0]["id"]

    confirmed = client.post(
        "/api/item-aliases/confirm",
        headers=auth,
        json={"canonical_line_id": order_line_id, "alias_line_id": invoice_line_id},
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["reanalyzed_chains"] == 1
    types = active_case_types(client, auth)
    assert "price_over_order" in types
    assert "unmatched_invoice_line" not in types
    aliases = client.get("/api/item-aliases", headers=auth).json()
    assert any(alias["normalized_alias"] == "Z900" for alias in aliases)


def test_same_description_and_year_do_not_override_different_explicit_skus(client, auth):
    supplier = "Conservative Matching Supplier"
    order = {
        "document_type": "order",
        "number": "PO-CONSERVATIVE-1",
        "supplier_name": supplier,
        "lines": [{"sku": "MODEL-A", "description": "Catalogo tecnico 2026", "quantity": 1, "unit_price": 10}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-CONSERVATIVE-1",
        "supplier_name": supplier,
        "references": {"order_numbers": ["PO-CONSERVATIVE-1"]},
        "lines": [{"sku": "MODEL-B", "description": "Catalogo tecnico 2026", "quantity": 1, "unit_price": 12}],
    }
    assert upload_payload(client, auth, "order.json", order).status_code == 201
    assert upload_payload(client, auth, "invoice.json", invoice).status_code == 201
    types = active_case_types(client, auth)
    assert "unmatched_invoice_line" in types
    assert "price_over_order" not in types
