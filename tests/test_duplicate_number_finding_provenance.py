from __future__ import annotations

import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase
from app.provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact


def _order_payload(number: str, *, suffix: str) -> bytes:
    return json.dumps(
        {
            "document_type": "order",
            "number": number,
            "document_date": "2026-08-28",
            "supplier_name": "Provenance Test Supplier",
            "supplier_vat": "IT00000000001",
            "lines": [
                {
                    "line_no": 1,
                    "sku": f"ITEM-{suffix}",
                    "description": f"Item {suffix}",
                    "quantity": 1,
                    "unit_price": 10,
                    "discount_rate": 0,
                    "tax_rate": 22,
                    "line_total": 10,
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _upload(client, auth, *, filename: str, source_number: str, suffix: str, override_number: str | None = None):
    data = {"number": override_number} if override_number is not None else {}
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, _order_payload(source_number, suffix=suffix), "application/json")},
        data=data,
    )


def test_duplicate_number_finding_links_direct_json_number_facts(client, auth):
    first = _upload(client, auth, filename="duplicate-a.json", source_number="DUP-100", suffix="A")
    second = _upload(client, auth, filename="duplicate-b.json", source_number="DUP-100", suffix="B")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    document_ids = {first.json()["document"]["id"], second.json()["document"]["id"]}

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "duplicate_document_number"))
        assert case is not None
        provenance = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert provenance is not None
        assert provenance.version == 1
        assert provenance.rule_id == "builtin:duplicate_document_number"
        assert provenance.rule_version == "1"
        assert len(provenance.rule_configuration_hash) == 64

        links = list(
            db.scalars(
                select(ProvenanceFindingFact).where(
                    ProvenanceFindingFact.tenant_id == case.tenant_id,
                    ProvenanceFindingFact.finding_id == provenance.id,
                )
            )
        )
        assert len(links) == 2
        facts = [db.get(ProvenanceFact, link.fact_id) for link in links]
        assert all(fact is not None for fact in facts)
        assert {fact.fact_key for fact in facts if fact is not None} == {
            f"document:{document_id}:number" for document_id in document_ids
        }
        assert {fact.value_json for fact in facts if fact is not None} == {'"DUP-100"'}


def test_duplicate_number_finding_provenance_is_fail_closed_for_override(client, auth):
    first = _upload(client, auth, filename="mixed-a.json", source_number="DUP-MIX", suffix="A")
    second = _upload(
        client,
        auth,
        filename="mixed-b.json",
        source_number="SOURCE-ONLY",
        suffix="B",
        override_number="DUP-MIX",
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "duplicate_document_number"))
        assert case is not None
        provenance = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert provenance is None


def test_duplicate_number_finding_provenance_versions_when_support_set_changes(client, auth):
    responses = [
        _upload(client, auth, filename=f"version-{suffix}.json", source_number="DUP-VER", suffix=suffix)
        for suffix in ("A", "B", "C")
    ]
    assert all(response.status_code == 201 for response in responses)

    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "duplicate_document_number"))
        assert case is not None
        versions = list(
            db.scalars(
                select(ProvenanceFinding)
                .where(
                    ProvenanceFinding.tenant_id == case.tenant_id,
                    ProvenanceFinding.case_id == case.id,
                )
                .order_by(ProvenanceFinding.version)
            )
        )
        assert [item.version for item in versions] == [1, 2]
        assert versions[1].supersedes_finding_id == versions[0].id
        latest_links = list(
            db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == versions[1].id))
        )
        assert len(latest_links) == 3
