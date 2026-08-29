from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ChainDocument, DiscrepancyCase, Document, OperationChain
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
_CURRENCY_MISMATCH_RULE_ID = "builtin:currency_mismatch"
_CURRENCY_MISMATCH_RULE_VERSION = "1"
_CURRENCY_MISMATCH_RULE_CONFIGURATION_HASH = hashlib.sha256(
    json.dumps(
        {
            "scope": "operation_chain",
            "input": "all_non_empty_document_currency_values",
            "comparison": "distinct_value_count_gt_1",
            "support": "all_current_engine_inputs_require_direct_document_evidence",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
_CHAIN_ROLES = (
    "proposal",
    "order",
    "confirmation",
    "delivery",
    "invoice",
    "payment",
    "return",
    "credit_note",
)


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
            or origin.source_availability != "available"
            or origin.locator_status != "present"
            or origin.locator_type != "JSON_POINTER"
            or origin.locator_json != '{"pointer":"/number"}'
        ):
            return []
        ordered.append(fact)
    return ordered


def _supporting_currency_facts(
    db: Session,
    *,
    chain: OperationChain,
    all_documents: list[Document],
) -> list[ProvenanceFact]:
    documents_by_id = {document.id: document for document in all_documents if document.currency}
    documents = sorted(documents_by_id.values(), key=lambda document: document.id)
    if len({document.currency for document in documents}) < 2:
        return []

    fact_keys = [f"document:{document.id}:currency" for document in documents]
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
    ordered: list[ProvenanceFact] = []
    for document, fact_key in zip(documents, fact_keys, strict=True):
        fact = latest_by_key[fact_key]
        origin = origins.get(fact.origin_id)
        expected_value = json.dumps(document.currency, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if (
            fact.fact_type != "document.currency"
            or fact.value_json != expected_value
            or origin is None
            or origin.origin_type != "DOCUMENT_EVIDENCE"
            or origin.document_id != document.id
            or origin.source_ref != f"sha256:{document.file_hash}"
            or origin.source_availability != "available"
            or origin.locator_status != "present"
            or not origin.locator_type
            or not origin.locator_json
        ):
            return []
        if origin.locator_type == "JSON_POINTER" and origin.locator_json != '{"pointer":"/currency"}':
            return []
        ordered.append(fact)
    return ordered


def _current_chain_documents(db: Session, chain: OperationChain) -> list[Document]:
    links = list(
        db.execute(
            select(ChainDocument.role, ChainDocument.document_id, ChainDocument.sequence_no)
            .where(
                ChainDocument.tenant_id == chain.tenant_id,
                ChainDocument.chain_id == chain.id,
            )
            .order_by(ChainDocument.role, ChainDocument.sequence_no, ChainDocument.document_id)
        )
    )
    linked_by_role: dict[str, list[str]] = defaultdict(list)
    for role, document_id, _sequence_no in links:
        linked_by_role[role].append(document_id)

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for role in _CHAIN_ROLES:
        role_ids = linked_by_role.get(role, [])
        if not role_ids:
            primary_id = getattr(chain, f"{role}_document_id", None)
            role_ids = [primary_id] if primary_id else []
        for document_id in role_ids:
            if document_id not in seen:
                seen.add(document_id)
                ordered_ids.append(document_id)
    if not ordered_ids:
        return []

    documents = list(
        db.scalars(
            select(Document).where(
                Document.tenant_id == chain.tenant_id,
                Document.id.in_(ordered_ids),
            )
        )
    )
    by_id = {document.id: document for document in documents}
    return [by_id[document_id] for document_id in ordered_ids if document_id in by_id]


def _linked_facts(db: Session, finding: ProvenanceFinding) -> list[ProvenanceFact] | None:
    linked_fact_ids = list(
        db.scalars(
            select(ProvenanceFindingFact.fact_id).where(
                ProvenanceFindingFact.tenant_id == finding.tenant_id,
                ProvenanceFindingFact.finding_id == finding.id,
            )
        )
    )
    if not linked_fact_ids or len(set(linked_fact_ids)) != len(linked_fact_ids):
        return None
    linked_facts = list(
        db.scalars(
            select(ProvenanceFact).where(
                ProvenanceFact.tenant_id == finding.tenant_id,
                ProvenanceFact.id.in_(linked_fact_ids),
            )
        )
    )
    if len(linked_facts) != len(linked_fact_ids):
        return None
    return linked_facts


def duplicate_number_finding_matches_current_support(
    db: Session,
    *,
    finding: ProvenanceFinding,
) -> bool:
    """Return True only while a duplicate-number finding exactly matches current complete evidence."""
    if finding.rule_id != _DUPLICATE_NUMBER_RULE_ID:
        return False

    case = db.get(DiscrepancyCase, finding.case_id)
    if case is None or case.tenant_id != finding.tenant_id or case.case_type != "duplicate_document_number":
        return False
    chain = db.get(OperationChain, case.chain_id)
    if chain is None or chain.tenant_id != finding.tenant_id:
        return False

    linked_facts = _linked_facts(db, finding)
    if linked_facts is None or len(linked_facts) < 2:
        return False

    document_ids: list[str] = []
    numbers: set[str] = set()
    for fact in linked_facts:
        parts = fact.fact_key.split(":", 2)
        if len(parts) != 3 or parts[0] != "document" or parts[2] != "number":
            return False
        try:
            number = json.loads(fact.value_json)
        except (TypeError, json.JSONDecodeError):
            return False
        if not isinstance(number, str) or not number:
            return False
        document_ids.append(parts[1])
        numbers.add(number)
    if len(numbers) != 1 or len(set(document_ids)) != len(document_ids):
        return False

    linked_documents = list(
        db.scalars(
            select(Document).where(
                Document.tenant_id == finding.tenant_id,
                Document.id.in_(document_ids),
            )
        )
    )
    if len(linked_documents) != len(document_ids):
        return False
    document_types = {document.document_type for document in linked_documents}
    if len(document_types) != 1:
        return False

    number = next(iter(numbers))
    document_type = next(iter(document_types))
    current_facts = _supporting_number_facts(
        db,
        chain=chain,
        finding_key=f"duplicate-number:{document_type}:{number}",
        all_documents=_current_chain_documents(db, chain),
    )
    return len(current_facts) == len(linked_facts) and {fact.id for fact in current_facts} == {
        fact.id for fact in linked_facts
    }


def currency_mismatch_finding_matches_current_support(
    db: Session,
    *,
    finding: ProvenanceFinding,
) -> bool:
    """Return True only while the mismatch exactly matches all current direct currency inputs."""
    if finding.rule_id != _CURRENCY_MISMATCH_RULE_ID:
        return False

    case = db.get(DiscrepancyCase, finding.case_id)
    if case is None or case.tenant_id != finding.tenant_id or case.case_type != "currency_mismatch":
        return False
    chain = db.get(OperationChain, case.chain_id)
    if chain is None or chain.tenant_id != finding.tenant_id:
        return False

    linked_facts = _linked_facts(db, finding)
    if linked_facts is None or len(linked_facts) < 2:
        return False
    values: set[str] = set()
    document_ids: set[str] = set()
    for fact in linked_facts:
        parts = fact.fact_key.split(":", 2)
        if len(parts) != 3 or parts[0] != "document" or parts[2] != "currency":
            return False
        try:
            value = json.loads(fact.value_json)
        except (TypeError, json.JSONDecodeError):
            return False
        if not isinstance(value, str) or not value:
            return False
        if parts[1] in document_ids:
            return False
        document_ids.add(parts[1])
        values.add(value)
    if len(values) < 2:
        return False

    current_facts = _supporting_currency_facts(
        db,
        chain=chain,
        all_documents=_current_chain_documents(db, chain),
    )
    return len(current_facts) == len(linked_facts) and {fact.id for fact in current_facts} == {
        fact.id for fact in linked_facts
    }


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


def record_currency_mismatch_finding_provenance(
    db: Session,
    *,
    chain: OperationChain,
    case: DiscrepancyCase,
    finding_case_type: str,
    finding_key: str,
    all_documents: list[Document],
) -> None:
    if finding_case_type != "currency_mismatch" or finding_key != "chain-currency":
        return

    facts = _supporting_currency_facts(
        db,
        chain=chain,
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
            current.rule_id == _CURRENCY_MISMATCH_RULE_ID
            and current.rule_version == _CURRENCY_MISMATCH_RULE_VERSION
            and current.rule_configuration_hash == _CURRENCY_MISMATCH_RULE_CONFIGURATION_HASH
            and linked_fact_ids == set(fact_ids)
        ):
            return

    record_finding(
        db,
        tenant_id=chain.tenant_id,
        case_id=case.id,
        input_fact_ids=fact_ids,
        rule_id=_CURRENCY_MISMATCH_RULE_ID,
        rule_version=_CURRENCY_MISMATCH_RULE_VERSION,
        rule_configuration_hash=_CURRENCY_MISMATCH_RULE_CONFIGURATION_HASH,
        supersedes_finding_id=current.id if current is not None else None,
    )
