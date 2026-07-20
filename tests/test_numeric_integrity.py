import json

from app.parsers.base import safe_float


def test_non_finite_numbers_are_rejected_by_parser_helper():
    assert safe_float("NaN", 7.0) == 7.0
    assert safe_float("Infinity", 8.0) == 8.0
    assert safe_float("-Infinity", 9.0) == 9.0


def test_decimal_storage_avoids_binary_money_false_positive(client, auth):
    order = {
        "document_type": "order",
        "number": "DEC-1",
        "supplier_name": "Decimal Supplier",
        "lines": [{"sku": "D", "quantity": 3, "unit_price": 0.1, "line_total": 0.3}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "DEC-I",
        "supplier_name": "Decimal Supplier",
        "references": {"order_numbers": ["DEC-1"]},
        "lines": [{"sku": "D", "quantity": 3, "unit_price": 0.1, "line_total": 0.3}],
    }
    for name, payload in (("decimal-order.json", order), ("decimal-invoice.json", invoice)):
        response = client.post(
            "/api/documents/upload",
            headers=auth,
            files={"file": (name, json.dumps(payload).encode(), "application/json")},
        )
        assert response.status_code == 201
        assert response.json()["document"]["lines"][0]["line_total"] == 0.3
    active_types = {
        case["case_type"] for case in client.get("/api/cases", headers=auth).json() if case["status"] != "superseded"
    }
    assert "line_total_mismatch" not in active_types
