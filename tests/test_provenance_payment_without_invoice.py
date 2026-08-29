from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, OperationChain
from app.provenance_models import (
    ProvenanceFact,
    ProvenanceFinding,
    ProvenanceFindingFact,
    ProvenanceJudgment,
    ProvenanceOrigin,
)
from app.services.payment_without_invoice_provenance import (
    payment_without_invoice_finding_matches_current_support,
)
from app.services.rules import analyze_chain


def _payload(*, number: str, total: str, explicit_line_total: bool = True, document_type: str = "payment") -> bytes:
    line: dict[str, object] = {
        "line_no": 1,
        "sku": "PAY-WITHOUT-INV-SKU",
        "description": "Payment without invoice snapshot qualification",
        "quantity": "1",
        "unit_of_measure": "EA",
        "unit_price": total,
        "price_base_quantity": "1",
        "discount_rate": "0",
        "tax_rate": "0",
    }
    if explicit_line_total:
        line["line_total"] = total
    return json.dumps(
        {
            "document_type": document_type,
            "number": number,
            "document_date": "2026-08-29",
            "supplier_name": "Absence Snapshot Supplier",
            "supplier_vat": "IT00000000055",
            "currency": "EUR",
            "lines": [line],
        }
    ).encode("utf-8")


def _upload(
    client,
    auth,
    *,
    number: str,
    total: str,
    explicit_line_total: bool = True,
    document_type: str = "payment",
):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"{number}.json",
                _payload(
                    number=number,
                    total=total,
                    explicit_line_total=explicit_line_total,
                    document_type=document_type,
                ),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response


def _case(db) -> DiscrepancyCase | None:
    return db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "payment_without_invoice"))


def _findings(db, case: DiscrepancyCase) -> list[ProvenanceFinding]:
    return list(
        db.scalars(
            select(ProvenanceFinding)
            .where(ProvenanceFinding.tenant_id == case.tenant_id, ProvenanceFinding.case_id == case.id)
            .order_by(ProvenanceFinding.version)
        )
    )


def _linked_fact(db, finding: ProvenanceFinding) -> ProvenanceFact:
    fact_id = db.scalar(
        select(ProvenanceFindingFact.fact_id).where(
            ProvenanceFindingFact.tenant_id == finding.tenant_id,
            ProvenanceFindingFact.finding_id == finding.id,
        )
    )
    assert fact_id is not None
    fact = db.get(ProvenanceFact, fact_id)
    assert fact is not None
    return fact


def test_payment_without_invoice_binds_exact_snapshot_and_current_human_judgment(client, auth):
    _upload(client, auth, number="PAY-ABS-E2E", total="125.00")

    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("125.00")
        findings = _findings(db, case)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.rule_id == "builtin:payment_without_invoice"
        assert finding.rule_version == "1"
        assert len(finding.rule_configuration_hash) == 64
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True

        fact = _linked_fact(db, finding)
        assert fact.fact_type == "operation_chain.payment_without_invoice_snapshot"
        snapshot = json.loads(fact.value_json)
        assert snapshot["claim_boundary"].startswith("no invoice is linked in this exact operation-chain snapshot")
        assert snapshot["invoice_document_ids"] == []
        assert len(snapshot["payment_document_ids"]) == 1
        assert snapshot["predicate"] == {"invoice_role_empty": True, "payments_present": True}
        assert snapshot["matcher"]["id"] == "builtin:operation_chain_matching"
        assert snapshot["matcher"]["version"] == "1"
        assert len(snapshot["matcher"]["configuration_hash"]) == 64
        assert snapshot["rule"]["id"] == "builtin:payment_without_invoice"
        assert snapshot["payment_total"] == {
            "case_amount_estimate": "125.00",
            "status": "known",
            "value": "125.00",
        }
        origin = db.get(ProvenanceOrigin, fact.origin_id)
        assert origin is not None
        assert origin.origin_type == "SYSTEM_OBSERVATION"
        assert origin.engine_id == "builtin:operation_chain_matching"
        assert origin.engine_version == "1"
        assert origin.configuration_hash is not None and len(origin.configuration_hash) == 64
        assert origin.source_ref is not None and origin.source_ref.startswith("sha256:")
        case_id = case.id
        finding_id = finding.id

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Confirmed against the exact current matching snapshot."},
    )
    assert reviewed.status_code == 200, reviewed.text
    with SessionLocal() as db:
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert judgment is not None
        assert judgment.decision == "confirmed"


def test_payment_without_invoice_reanalysis_is_idempotent_and_membership_change_versions_snapshot(client, auth):
    _upload(client, auth, number="PAY-ABS-V1", total="100.00")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        first = _findings(db, case)
        assert [finding.version for finding in first] == [1]
        first_finding_id = first[0].id
        first_fact = _linked_fact(db, first[0])
        chain = db.get(OperationChain, case.chain_id)
        assert chain is not None
        analyze_chain(db, chain)
        db.flush()
        assert [finding.version for finding in _findings(db, case)] == [1]
        facts = list(
            db.scalars(
                select(ProvenanceFact)
                .where(ProvenanceFact.fact_key == f"operation_chain:{chain.id}:payment_without_invoice_snapshot")
                .order_by(ProvenanceFact.version)
            )
        )
        assert [fact.version for fact in facts] == [1]

    _upload(client, auth, number="PAY-ABS-V2", total="30.00")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("130.00")
        findings = _findings(db, case)
        assert [finding.version for finding in findings] == [1, 2]
        assert findings[1].supersedes_finding_id == first_finding_id
        assert payment_without_invoice_finding_matches_current_support(db, finding=findings[0]) is False
        assert payment_without_invoice_finding_matches_current_support(db, finding=findings[1]) is True
        current_fact = _linked_fact(db, findings[1])
        assert current_fact.version == 2
        assert current_fact.supersedes_fact_id == first_fact.id
        snapshot = json.loads(current_fact.value_json)
        assert len(snapshot["payment_document_ids"]) == 2
        assert snapshot["payment_total"]["case_amount_estimate"] == "130.00"


def test_payment_without_invoice_invoice_arrival_makes_old_absence_support_stale(client, auth):
    _upload(client, auth, number="PAY-ABS-STALE", total="80.00")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        finding = _findings(db, case)[0]
        case_id = case.id
        finding_id = finding.id
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True

    _upload(client, auth, number="INV-ABS-STALE", total="80.00", document_type="invoice")
    with SessionLocal() as db:
        case = db.get(DiscrepancyCase, case_id)
        finding = db.get(ProvenanceFinding, finding_id)
        assert case is not None and finding is not None
        assert case.status == "superseded"
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False


def test_payment_without_invoice_unknown_amount_still_proves_snapshot_scoped_absence(client, auth):
    _upload(client, auth, number="PAY-ABS-UNKNOWN", total="42.00", explicit_line_total=False)
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("0.00")
        finding = _findings(db, case)[0]
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True
        snapshot = json.loads(_linked_fact(db, finding).value_json)
        assert snapshot["payment_total"] == {
            "case_amount_estimate": "0.00",
            "status": "numeric_inputs_unavailable",
            "value": None,
        }


def test_payment_without_invoice_snapshot_and_metadata_mutation_fail_closed(client, auth):
    _upload(client, auth, number="PAY-ABS-HOSTILE", total="75.00")
    with SessionLocal() as db:
        case = _case(db)
        assert case is not None
        finding = _findings(db, case)[0]
        fact = _linked_fact(db, finding)
        origin = db.get(ProvenanceOrigin, fact.origin_id)
        assert origin is not None

        original_value = fact.value_json
        snapshot = json.loads(original_value)
        snapshot["invoice_document_ids"] = ["forged-invoice"]
        fact.value_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        fact.value_json = original_value

        original_engine_version = origin.engine_version
        origin.engine_version = "stale"
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        origin.engine_version = original_engine_version

        original_configuration_hash = origin.configuration_hash
        origin.configuration_hash = "0" * 64
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        origin.configuration_hash = original_configuration_hash

        original_rule_version = finding.rule_version
        finding.rule_version = "stale"
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        finding.rule_version = original_rule_version

        original_amount = case.amount_estimate
        case.amount_estimate = Decimal("74.99")
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        case.amount_estimate = original_amount
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True
