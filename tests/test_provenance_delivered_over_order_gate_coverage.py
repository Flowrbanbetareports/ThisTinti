from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.services.delivered_over_order_provenance import _fact_value_matches, _raw_locator


def test_raw_locator_rejects_malformed_non_object_and_non_mapping_shapes():
    line = SimpleNamespace(raw_json="{")
    assert _raw_locator(line, "quantity") is None

    line.raw_json = "[]"
    assert _raw_locator(line, "quantity") is None

    line.raw_json = '{"_source_locators": []}'
    assert _raw_locator(line, "quantity") is None

    line.raw_json = '{"_source_locators": {"quantity": "not-a-locator"}}'
    assert _raw_locator(line, "quantity") is None


def test_fact_value_matches_fails_closed_for_invalid_json_and_invalid_numeric_value():
    line = SimpleNamespace(quantity=Decimal("1"), unit_of_measure="EA")

    malformed = SimpleNamespace(value_json="{")
    assert _fact_value_matches(malformed, line, "quantity") is False

    non_numeric = SimpleNamespace(value_json='"not-a-number"')
    assert _fact_value_matches(non_numeric, line, "quantity") is False

    wrong_text_type = SimpleNamespace(value_json="1")
    assert _fact_value_matches(wrong_text_type, line, "unit_of_measure") is False
