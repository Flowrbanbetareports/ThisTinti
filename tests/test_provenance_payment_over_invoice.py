from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, DocumentLine, OperationChain, ReviewDecision
from app.provenance_models import (
    ProvenanceFact,
    ProvenanceFinding,
    ProvenanceFindingFact,
    ProvenanceJudgment,
    ProvenanceOrigin,
)
import app.services.payment_over_invoice_provenance as poi
from app.services.payment_over_invoice_provenance import payment_over_invoice_finding_matches_current_support
from app.services.rules import analyze_chain


def _payload(
    *,
    document_type: str,
    number: str,
    total: str,
    explicit_line_total: bool = True,
    invoice_number: str | None = None,
) -> bytes:
    line: dict[str, object] = {
        "line_no": 1,
        "sku": f"PAY-PROV-{number}",
        "description": f"Payment over invoice provenance {number}",
        "quantity": "1",
        "unit_of_measure": "EA",
        "unit_price": total,
        "price_base_quantity": "1",
        "discount_rate": "0",
        "tax_rate": "0",
    }
    if explicit_line_total:
        line["line_total"] = total
    payload: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-29",
        "supplier_name": "Payment Provenance Supplier",
        "supplier_vat": "IT00000000044",
        "currency": "EUR",
        "lines": [line],
    }
    if invoice_number is not None:
        payload["references"] = {"invoice_numbers": [invoice_number]}
    return json.dumps(payload).encode("utf-8")


def _upload(
    client,
    auth,
    *,
    document_type: str,
    number: str,
    total: str,
    explicit_line_total: bool = True,
    invoice_number: str | None = None,
):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"{number}.json",
                _payload(
                    document_type=document_type,
                    number=number,
                    total=total,
                    explicit_line_total=explicit_line_total,
                    invoice_number=invoice_number,
                ),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response


def _upload_overpayment(
    client,
    auth,
    *,
    suffix: str,
    invoice_total: str = "100.00",
    payment_total: str = "125.00",
    payment_explicit: bool = True,
) -> None:
    invoice_number = f"INV-PAY-PROV-{suffix}"
    _upload(
        client,
        auth,
        document_type="invoice",
        number=invoice_number,
        total=invoice_total,
    )
    _upload(
        client,
        auth,
        document_type="payment",
        number=f"PAY-PROV-{suffix}",
        total=payment_total,
        explicit_line_total=payment_explicit,
        invoice_number=invoice_number,
    )


def _case(db) -> DiscrepancyCase | None:
    return db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "payment_over_invoice"))


def _findings(db, case: DiscrepancyCase) -> list[ProvenanceFinding]:
    return list(
        db.scalars(
            select(ProvenanceFinding)
            .where(ProvenanceFinding.tenant_id == case.tenant_id, ProvenanceFinding.case_id == case.id)
            .order_by(ProvenanceFinding.version)
        )
    )


def test_payment_over_invoice_binds_exact_totals_and_current_human_judgment(client, auth):
    _upload_overpayment(client, auth, suffix="E2E")

    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("25.00")
        findings = _findings(db, case)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.rule_id == "builtin:payment_over_invoice"
        assert finding.rule_version == "1"
        assert len(finding.rule_configuration_hash) == 64
        assert payment_over_invoice_finding_matches_current_support(db, finding=finding) is True
        links = list(db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == finding.id)))
        assert len(links) == 2
        facts = [db.get(ProvenanceFact, link.fact_id) for link in links]
        assert all(fact is not None for fact in facts)
        assert {fact.fact_type for fact in facts if fact is not None} == {"document_line.line_total"}
        for fact in facts:
            assert fact is not None
            origin = db.get(ProvenanceOrigin, fact.origin_id)
            assert origin is not None
            assert origin.origin_type == "DOCUMENT_EVIDENCE"
            assert origin.source_availability == "available"
            assert origin.locator_status == "present"
            assert origin.locator_type == "JSON_POINTER"
            assert origin.engine_id == "native-json-parser"
            assert origin.engine_version == "1"
        case_id = case.id
        finding_id = finding.id

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Exact current invoice and payment totals checked."},
    )
    assert reviewed.status_code == 200, reviewed.text
    with SessionLocal() as db:
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert judgment is not None
        assert judgment.decision == "confirmed"


def test_payment_over_invoice_fails_closed_when_payment_total_is_derived_not_direct(client, auth):
    _upload_overpayment(client, auth, suffix="DERIVED", payment_explicit=False)
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("25.00")
        assert _findings(db, case) == []


def test_payment_over_invoice_reanalysis_is_idempotent_and_new_payment_versions_support(client, auth):
    suffix = "VERSION"
    invoice_number = f"INV-PAY-PROV-{suffix}"
    _upload_overpayment(client, auth, suffix=suffix)
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        first = _findings(db, case)
        assert [finding.version for finding in first] == [1]
        first_id = first[0].id
        chain = db.get(OperationChain, case.chain_id)
        assert chain is not None
        analyze_chain(db, chain)
        db.flush()
        assert [finding.version for finding in _findings(db, case)] == [1]

    _upload(
        client,
        auth,
        document_type="payment",
        number="PAY-PROV-VERSION-2",
        total="5.00",
        invoice_number=invoice_number,
    )
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("30.00")
        findings = _findings(db, case)
        assert [finding.version for finding in findings] == [1, 2]
        assert findings[1].supersedes_finding_id == first_id
        assert payment_over_invoice_finding_matches_current_support(db, finding=findings[0]) is False
        assert payment_over_invoice_finding_matches_current_support(db, finding=findings[1]) is True


def test_payment_over_invoice_rejects_unavailable_support_before_human_binding(client, auth):
    _upload_overpayment(client, auth, suffix="UNAVAILABLE")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        finding = _findings(db, case)[0]
        fact_id = db.scalar(select(ProvenanceFindingFact.fact_id).where(ProvenanceFindingFact.finding_id == finding.id))
        assert fact_id is not None
        fact = db.get(ProvenanceFact, fact_id)
        assert fact is not None
        origin = db.get(ProvenanceOrigin, fact.origin_id)
        assert origin is not None
        origin.source_availability = "external_unavailable"
        db.commit()
        assert payment_over_invoice_finding_matches_current_support(db, finding=finding) is False
        case_id = case.id
        finding_id = finding.id

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Must not bind stale payment provenance."},
    )
    assert reviewed.status_code == 409, reviewed.text
    with SessionLocal() as db:
        assert db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)) is None
        assert db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id)) is None
        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == "open"


def test_payment_over_invoice_rejects_support_marked_missing_by_numeric_provenance(client, auth):
    _upload_overpayment(client, auth, suffix="NUMERIC-MISSING")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        finding = _findings(db, case)[0]
        fact_id = db.scalar(select(ProvenanceFindingFact.fact_id).where(ProvenanceFindingFact.finding_id == finding.id))
        assert fact_id is not None
        fact = db.get(ProvenanceFact, fact_id)
        assert fact is not None
        line_id = fact.fact_key.split(":", 2)[1]
        line = db.get(DocumentLine, line_id)
        assert line is not None
        raw = json.loads(line.raw_json)
        raw.setdefault("numeric_provenance", {})["line_total"] = "missing"
        line.raw_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        db.commit()
        assert payment_over_invoice_finding_matches_current_support(db, finding=finding) is False
        case_id = case.id
        finding_id = finding.id

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Missing numeric support must fail closed."},
    )
    assert reviewed.status_code == 409, reviewed.text
    with SessionLocal() as db:
        assert db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id)) is None
        assert db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id)) is None
        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == "open"


def test_payment_over_invoice_malformed_support_and_metadata_fail_closed(client, auth):
    _upload_overpayment(client, auth, suffix="HOSTILE")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        finding = _findings(db, case)[0]
        chain = db.get(OperationChain, case.chain_id)
        assert chain is not None
        fact_id = db.scalar(select(ProvenanceFindingFact.fact_id).where(ProvenanceFindingFact.finding_id == finding.id))
        assert fact_id is not None
        fact = db.get(ProvenanceFact, fact_id)
        assert fact is not None
        line = db.get(DocumentLine, fact.fact_key.split(":", 2)[1])
        assert line is not None

        original_raw = line.raw_json
        line.raw_json = "{"
        assert poi._raw_locator(line) is None
        line.raw_json = "[]"
        assert poi._raw_locator(line) is None
        line.raw_json = original_raw

        original_value = fact.value_json
        fact.value_json = "not-json"
        assert poi._fact_value_matches(fact, line) is False
        fact.value_json = original_value

        original_amount = case.amount_estimate
        case.amount_estimate = Decimal("24.99")
        assert payment_over_invoice_finding_matches_current_support(db, finding=finding) is False
        case.amount_estimate = original_amount

        original_rule_version = finding.rule_version
        finding.rule_version = "stale"
        assert payment_over_invoice_finding_matches_current_support(db, finding=finding) is False
        finding.rule_version = original_rule_version

        poi.record_payment_over_invoice_finding_provenance(
            db,
            chain=chain,
            case=case,
            finding_case_type="currency_mismatch",
            finding_key="payment-over-invoice",
        )
        poi.record_payment_over_invoice_finding_provenance(
            db,
            chain=chain,
            case=case,
            finding_case_type="payment_over_invoice",
            finding_key="wrong-key",
        )
        original_fingerprint = case.fingerprint
        case.fingerprint = "wrong-fingerprint"
        poi.record_payment_over_invoice_finding_provenance(
            db,
            chain=chain,
            case=case,
            finding_case_type="payment_over_invoice",
            finding_key="payment-over-invoice",
        )
        case.fingerprint = original_fingerprint
        assert payment_over_invoice_finding_matches_current_support(db, finding=finding) is True
