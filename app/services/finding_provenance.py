from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DiscrepancyCase, Document, OperationChain
from ..provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceOrigin
from .provenance import record_finding


_DUPLICATE_NUMBER_RULE_ID = "builtin:duplicate_document_number"
_DUPLICATE_NUMBER_RULE_VERSION = "1"
_DUPLICATE_NUMBER_RULE_CONFIGURATION_HASH = hashlib.sha256(
    json.dumps(
        {
            "scope": "operation_chain",
            "document_type_scope": "same",
            "number_comparison": "exact_non_empty",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def _supporting_number_facts(
    db: Session,
    *,
    chain: OperationChain,
    finding_key: str,
    all_documents: list[Document],
) -> list[ProvenanceFact]:
    parts = finding_key.split(":", 2)
    if len(parts) != 3 or parts[0] != "duplicate-number":
        return []
    document_type, number = parts[1], parts[2]
    documents = sorted(
        [
            document
            for document in all_documents
            if document.document_type == document_type and document.number == number
        ],
        key=lambda document: document.id,
    )
    if len(documents) < 2:
        return []

    fact_keys = [f"document:{document.id}:number" for document in documents]
    candidates = list(
        db.scalars(
            select(ProvenanceFact).where(
                ProvenanceFact.tenant_id == chain.tenant_id,
                ProvenanceFact.fact_key.in_(fact_keys),
            )
        )
    )
    latest_by_key: dict[str, ProvenanceFact] = {}
    for fact in candidates:
        current = latest_by_key.get(fact.fact_key)
        if current is None or fact.version > current.version:
            latest_by_key[fact.fact_key] = fact
    if set(latest_by_key) != set(fact_keys):
        return []

    origin_ids = {fact.origin_id for fact in latest_by_key.values()}
    origins = {
        origin.id: origin
        for origin in db.scalars(
            select(ProvenanceOrigin).where(
                ProvenanceOrigin.tenant_id == chain.tenant_id,
                ProvenanceOrigin.id.in_(origin_ids),
            )
        )
    }
    expected_value = json.dumps(number, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ordered: list[ProvenanceFact] = []
    for document, fact_key in zip(documents, fact_keys, strict=True):
        fact = latest_by_key[fact_key]
        origin = origins.get(fact.origin_id)
        if (
            fact.value_json != expected_value
            or origin is None
            or origin.origin_type != "DOCUMENT_EVIDENCE"
            or origin.document_id != document.id
            or origin.locator_status != "present"
            or origin.locator_type != "JSON_POINTER"
            or origin.locator_json != '{"pointer":"/number"}'
        ):
            return []
        ordered.append(fact)
    return ordered


def record_duplicate_number_finding_provenance(
    db: Session,
    *,
    chain: OperationChain,
    case: DiscrepancyCase,
    finding_case_type: str,
    finding_key: str,
    all_documents: list[Document],
) -> None:
    if finding_case_type != "duplicate_document_number":
        return

    facts = _supporting_number_facts(
        db,
        chain=chain,
        finding_key=finding_key,
        all_documents=all_documents,
    )
    if len(facts) < 2:
        return

    fact_ids = [fact.id for fact in facts]
    current = db.scalar(
        select(ProvenanceFinding)
        .where(
            ProvenanceFinding.tenant_id == chain.tenant_id,
            ProvenanceFinding.case_id == case.id,
        )
        .order_by(ProvenanceFinding.version.desc())
    )
    if current is not None:
        linked_fact_ids = set(
            db.scalars(
                select(ProvenanceFindingFact.fact_id).where(
                    ProvenanceFindingFact.tenant_id == chain.tenant_id,
                    ProvenanceFindingFact.finding_id == current.id,
                )
            )
        )
        if (
            current.rule_id == _DUPLICATE_NUMBER_RULE_ID
            and current.rule_version == _DUPLICATE_NUMBER_RULE_VERSION
            and current.rule_configuration_hash == _DUPLICATE_NUMBER_RULE_CONFIGURATION_HASH
            and linked_fact_ids == set(fact_ids)
        ):
            return

    record_finding(
        db,
        tenant_id=chain.tenant_id,
        case_id=case.id,
        input_fact_ids=fact_ids,
        rule_id=_DUPLICATE_NUMBER_RULE_ID,
        rule_version=_DUPLICATE_NUMBER_RULE_VERSION,
        rule_configuration_hash=_DUPLICATE_NUMBER_RULE_CONFIGURATION_HASH,
        supersedes_finding_id=current.id if current is not None else None,
    )
