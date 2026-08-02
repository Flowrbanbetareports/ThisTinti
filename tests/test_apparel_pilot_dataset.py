from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.schemas import ValidationDatasetPayload


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "samples" / "pilot_apparel_30_synthetic.json"


def _family(identifier: str) -> str:
    for prefix in (
        "clean-",
        "multi-clean-",
        "quantity-over-",
        "price-over-",
        "discount-missing-",
        "unmatched-line-",
        "return-no-credit-",
        "partial-credit-",
        "ambiguous-sku-",
    ):
        if identifier.startswith(prefix):
            return prefix
    raise AssertionError(f"Unknown scenario family: {identifier}")


def test_apparel_pre_pilot_has_thirty_independent_scenarios() -> None:
    raw = json.loads(DATASET.read_text(encoding="utf-8"))
    payload = ValidationDatasetPayload.model_validate(raw)

    assert payload.evidence_level == "synthetic"
    assert payload.automation_eligible is False
    assert len(payload.scenarios) == 30
    assert len({scenario.id for scenario in payload.scenarios}) == 30
    assert sum(len(scenario.documents) for scenario in payload.scenarios) == 100
    assert sum(len(scenario.expected) for scenario in payload.scenarios) == 26

    families = Counter(_family(scenario.id) for scenario in payload.scenarios)
    assert families == {
        "clean-": 6,
        "multi-clean-": 2,
        "quantity-over-": 5,
        "price-over-": 4,
        "discount-missing-": 4,
        "unmatched-line-": 3,
        "return-no-credit-": 2,
        "partial-credit-": 2,
        "ambiguous-sku-": 2,
    }


def test_apparel_pre_pilot_is_scoped_and_contains_no_real_identity_fields() -> None:
    raw = json.loads(DATASET.read_text(encoding="utf-8"))
    payload = ValidationDatasetPayload.model_validate(raw)
    document_types = {
        str(document.content.get("document_type"))
        for scenario in payload.scenarios
        for document in scenario.documents
    }
    serialized = DATASET.read_text(encoding="utf-8").casefold()

    assert document_types <= {
        "order",
        "delivery",
        "invoice",
        "return",
        "credit_note",
    }
    for prohibited in (
        "supplier_vat",
        "iban",
        "email",
        "tax_code",
        "phone",
    ):
        assert prohibited not in serialized
