from decimal import Decimal

from app.services.rules import _display_decimal, _line_evidence


def test_decimal_presentation_removes_storage_scale_without_rounding_meaningful_digits():
    assert _display_decimal(Decimal("5.00000000")) == "5"
    assert _display_decimal(Decimal("120.00000000")) == "120"
    assert _display_decimal(Decimal("8.00"), max_places=2) == "8"
    assert _display_decimal(Decimal("12.345678"), max_places=4) == "12.3457"
    assert _display_decimal(Decimal("-0.000000")) == "0"


def test_decimal_evidence_uses_human_scale_but_keeps_non_numeric_values():
    evidence = _line_evidence(None, "quantity", Decimal("5.00000000"), Decimal("4.50000000"))
    assert evidence["observed_value"] == "5"
    assert evidence["expected_value"] == "4.5"
    textual = _line_evidence(None, "status", "pending", "confirmed")
    assert textual["observed_value"] == "pending"
    assert textual["expected_value"] == "confirmed"
