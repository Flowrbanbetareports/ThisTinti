import json
from datetime import date
from decimal import Decimal

import pytest

from app.parsers.base import (
    ParseError,
    parse_date,
    parse_decimal_field,
    parse_file,
    parse_integer_field,
    safe_decimal,
    safe_float,
)


def test_non_finite_numbers_are_rejected_by_parser_helper():
    for value in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ParseError, match="finito"):
            safe_float(value, 7.0)


def test_decimal_helper_preserves_locale_values_and_explicit_defaults():
    assert safe_decimal("1.234,50") == Decimal("1234.50")
    assert safe_decimal("12,5") == Decimal("12.5")
    assert safe_decimal(None, Decimal("7")) == Decimal("7")
    assert safe_decimal(Decimal("2.5")) == Decimal("2.5")


def test_decimal_helper_rejects_boolean_range_and_precision_errors():
    with pytest.raises(ParseError) as boolean_error:
        safe_decimal(True)
    assert "booleani" in boolean_error.value.reason
    with pytest.raises(ParseError, match="fuori intervallo"):
        parse_decimal_field("123456789", field="amount", max_integral_digits=8)
    with pytest.raises(ParseError, match="fuori intervallo"):
        parse_decimal_field("-1", field="rate", minimum=0)
    with pytest.raises(ParseError, match="fuori intervallo"):
        parse_decimal_field("101", field="rate", maximum=100)
    with pytest.raises(ParseError, match="mancante"):
        parse_integer_field(None, field="line_no")
    with pytest.raises(ParseError, match="intero"):
        parse_integer_field(-1, field="line_no", minimum=1)


def test_parser_helpers_cover_dates_and_unsupported_formats(tmp_path):
    expected = date(2026, 7, 25)
    assert parse_date(expected) is expected
    assert parse_date("not-a-date") is None
    unsupported = tmp_path / "document.txt"
    unsupported.write_text("text", encoding="utf-8")
    with pytest.raises(ParseError, match="non supportato"):
        parse_file(unsupported, unsupported.name, "text/plain", {})


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
