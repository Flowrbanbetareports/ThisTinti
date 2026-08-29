from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace

import app.services.payment_over_invoice_provenance as poi


def test_payment_locator_shape_guards_fail_closed() -> None:
    line = SimpleNamespace(
        raw_json=json.dumps(
            {
                "numeric_provenance": {"line_total": "explicit"},
                "_source_locators": [],
            }
        )
    )
    assert poi._raw_locator(line) is None

    line.raw_json = json.dumps(
        {
            "numeric_provenance": {"line_total": "explicit"},
            "_source_locators": {"line_total": "not-a-locator-object"},
        }
    )
    assert poi._raw_locator(line) is None


def test_payment_fact_value_rejects_non_numeric_json_value() -> None:
    fact = SimpleNamespace(value_json=json.dumps("not-a-number"))
    line = SimpleNamespace(line_total=Decimal("125.00"))
    assert poi._fact_value_matches(fact, line) is False
