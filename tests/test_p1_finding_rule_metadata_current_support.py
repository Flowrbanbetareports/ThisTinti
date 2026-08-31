from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase
from app.provenance_models import ProvenanceFinding
from app.services.finding_provenance import (
    currency_mismatch_finding_matches_current_support,
    duplicate_number_finding_matches_current_support,
)


def _payload(
    *,
    document_type: str,
    number: str,
    currency: str = "EUR",
    order_number: str | None = None,
    suffix: str,
) -> bytes:
    data: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-31",
        "supplier_name": "Rule Metadata Test Supplier",
        "supplier_vat": "IT00000000031",
        "currency": currency,
        "lines": [
            {
                "line_no": 1,
                "sku": f"META-{suffix}",
                "description": f"Metadata test {suffix}",
                "quantity": 1,
                "unit_price": 10,
                "discount_rate": 0,
                "tax_rate": 22,
                "line_total": 10,
            }
        ],
    }
    if order_number is not None:
        data["references"] = {"order_numbers": [order_number]}
    return json.dumps(data).encode("utf-8")


def _upload(
    client,
    auth,
    *,
    document_type: str,
    number: str,
    currency: str = "EUR",
    order_number: str | None = None,
    suffix: str,
):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"metadata-{suffix}.json",
                _payload(
                    document_type=document_type,
                    number=number,
                    currency=currency,
                    order_number=order_number,
                    suffix=suffix,
                ),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response


def _finding_for(case_type: str) -> tuple[DiscrepancyCase, ProvenanceFinding]:
    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == case_type))
        assert case is not None
        finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert finding is not None
        db.expunge(case)
        db.expunge(finding)
        return case, finding


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    (("rule_version", "stale-version"), ("rule_configuration_hash", "0" * 64)),
)
def test_duplicate_current_support_rejects_rule_metadata_drift(client, auth, field, tampered_value):
    _upload(client, auth, document_type="order", number="META-DUP", suffix="dup-a")
    _upload(client, auth, document_type="order", number="META-DUP", suffix="dup-b")
    case, finding = _finding_for("duplicate_document_number")

    with SessionLocal() as db:
        finding = db.get(ProvenanceFinding, finding.id)
        assert finding is not None
        assert duplicate_number_finding_matches_current_support(db, finding=finding)

        setattr(finding, field, tampered_value)
        db.flush()

        assert not duplicate_number_finding_matches_current_support(db, finding=finding)
        assert finding.case_id == case.id


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    (("rule_version", "stale-version"), ("rule_configuration_hash", "0" * 64)),
)
def test_currency_current_support_rejects_rule_metadata_drift(client, auth, field, tampered_value):
    _upload(
        client,
        auth,
        document_type="order",
        number="META-PO",
        currency="EUR",
        suffix="currency-order",
    )
    _upload(
        client,
        auth,
        document_type="invoice",
        number="META-INV",
        currency="USD",
        order_number="META-PO",
        suffix="currency-invoice",
    )
    case, finding = _finding_for("currency_mismatch")

    with SessionLocal() as db:
        finding = db.get(ProvenanceFinding, finding.id)
        assert finding is not None
        assert currency_mismatch_finding_matches_current_support(db, finding=finding)

        setattr(finding, field, tampered_value)
        db.flush()

        assert not currency_mismatch_finding_matches_current_support(db, finding=finding)
        assert finding.case_id == case.id
