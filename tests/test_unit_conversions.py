from __future__ import annotations

import json


def _upload(client, auth, filename: str, payload: dict):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document"]


def _linked_pair(client, auth, order_line: dict, invoice_line: dict):
    supplier = "Unit Conversion Supplier"
    order = _upload(
        client,
        auth,
        "unit-order.json",
        {
            "document_type": "order",
            "number": "PO-UOM-1",
            "supplier_name": supplier,
            "lines": [order_line],
        },
    )
    invoice = _upload(
        client,
        auth,
        "unit-invoice.json",
        {
            "document_type": "invoice",
            "number": "INV-UOM-1",
            "supplier_name": supplier,
            "references": {"order_numbers": ["PO-UOM-1"]},
            "lines": [invoice_line],
        },
    )
    chains = client.get("/api/chains", headers=auth).json()
    chain = next(item for item in chains if order["id"] in item["documents"].get("order", []))
    assert invoice["id"] in chain["documents"].get("invoice", [])
    return chain


def test_convertible_units_do_not_create_false_quantity_or_price_cases(client, auth):
    chain = _linked_pair(
        client,
        auth,
        {"sku": "MASS-1", "quantity": 1, "unit_of_measure": "KG", "unit_price": 10, "line_total": 10},
        {
            "sku": "MASS-1",
            "quantity": 1000,
            "unit_of_measure": "G",
            "unit_price": 0.01,
            "line_total": 10,
        },
    )
    cases = client.get("/api/cases", headers=auth).json()
    types = {case["case_type"] for case in cases if case["chain_id"] == chain["id"] and case["status"] != "superseded"}
    assert "unit_mismatch" not in types
    assert "invoiced_over_received" not in types
    assert "price_over_order" not in types

    detail = client.get(f"/api/chains/{chain['id']}", headers=auth).json()
    row = detail["comparison"]["rows"][0]
    assert row["values"]["order"]["quantity"] == 1.0
    assert row["values"]["invoice"]["quantity"] == 1.0
    assert row["values"]["order"]["unit_price"] == 10.0
    assert row["values"]["invoice"]["unit_price"] == 10.0
    assert row["status"] == "ok"


def test_incompatible_units_block_misleading_economic_comparisons(client, auth):
    chain = _linked_pair(
        client,
        auth,
        {"sku": "MIXED-1", "quantity": 1, "unit_of_measure": "EA", "unit_price": 10, "line_total": 10},
        {"sku": "MIXED-1", "quantity": 2, "unit_of_measure": "KG", "unit_price": 20, "line_total": 40},
    )
    cases = client.get("/api/cases", headers=auth).json()
    types = {case["case_type"] for case in cases if case["chain_id"] == chain["id"] and case["status"] != "superseded"}
    assert "unit_mismatch" in types
    assert "invoiced_over_received" not in types
    assert "price_over_order" not in types

    detail = client.get(f"/api/chains/{chain['id']}", headers=auth).json()
    row = detail["comparison"]["rows"][0]
    assert row["status"] == "issue"
    assert "unità di misura incompatibili" in row["reasons"]
