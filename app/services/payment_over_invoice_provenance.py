from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import ChainDocument, DiscrepancyCase, Document, DocumentLine, OperationChain
from ..provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceOrigin
from .provenance import record_finding


_RULE_ID = "builtin:payment_over_invoice"
_RULE_VERSION = "1"
_RULE_CONFIGURATION_HASH = hashlib.sha256(
    json.dumps(
        {
            "scope": "current_operation_chain_invoice_and_payment_documents",
            "document_total": "money(sum(abs(explicit_line_total)))",
            "comparison": "payment_total_gt_invoice_total_plus_0.02",
            "amount": "payment_total_minus_invoice_total",
            "support": "all_current_invoice_and_payment_line_total inputs must be direct native JSON evidence",
            "missing_or_defaulted_inputs": "fail_closed",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
_MONEY_QUANTUM = Decimal("0.01")
_THRESHOLD = Decimal("0.02")
_ROLES = ("invoice", "payment")


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _role_documents(db: Session, chain: OperationChain) -> dict[str, list[Document]]:
    links = list(
        db.execute(
            select(ChainDocument.role, ChainDocument.document_id, ChainDocument.sequence_no)
            .where(
                ChainDocument.tenant_id == chain.tenant_id,
                ChainDocument.chain_id == chain.id,
                ChainDocument.role.in_(_ROLES),
            )
            .order_by(ChainDocument.role, ChainDocument.sequence_no, ChainDocument.document_id)
        )
    )
    linked: dict[str, list[str]] = {role: [] for role in _ROLES}
    for role, document_id, _sequence_no in links:
        linked[role].append(document_id)

    ordered_ids: list[str] = []
    for role in _ROLES:
        if not linked[role]:
            primary_id = getattr(chain, f"{role}_document_id", None)
            linked[role] = [primary_id] if primary_id else []
        ordered_ids.extend(linked[role])
    if not ordered_ids:
        return {role: [] for role in _ROLES}

    documents = list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.lines))
            .where(
                Document.tenant_id == chain.tenant_id,
                Document.id.in_(set(ordered_ids)),
            )
        )
    )
    by_id = {document.id: document for document in documents}
    return {role: [by_id[document_id] for document_id in linked[role] if document_id in by_id] for role in _ROLES}


def _raw_locator(line: DocumentLine) -> dict[str, object] | None:
    try:
        raw = json.loads(line.raw_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    locators = raw.get("_source_locators")
    if not isinstance(locators, dict):
        return None
    locator = locators.get("line_total")
    return locator if isinstance(locator, dict) else None


def _fact_value_matches(fact: ProvenanceFact, line: DocumentLine) -> bool:
    try:
        value = json.loads(fact.value_json)
        return Decimal(str(value)) == _decimal(line.line_total)
    except (InvalidOperation, TypeError, ValueError, json.JSONDecodeError):
        return False


def _direct_line_total_fact(
    db: Session,
    *,
    chain: OperationChain,
    document: Document,
    line: DocumentLine,
) -> ProvenanceFact | None:
    fact = db.scalar(
        select(ProvenanceFact)
        .where(
            ProvenanceFact.tenant_id == chain.tenant_id,
            ProvenanceFact.fact_key == f"document_line:{line.id}:line_total",
        )
        .order_by(ProvenanceFact.version.desc())
        .limit(1)
    )
    if fact is None or fact.fact_type != "document_line.line_total" or not _fact_value_matches(fact, line):
        return None
    origin = db.get(ProvenanceOrigin, fact.origin_id)
    locator = _raw_locator(line)
    if origin is None or locator is None:
        return None
    pointer = str(locator.get("pointer") or "")
    parts = pointer.split("/")
    if len(parts) != 4 or parts[:2] != ["", "lines"] or not parts[2].isdigit() or parts[3] != "line_total":
        return None
    if (
        locator.get("locator_type") != "JSON_POINTER"
        or locator.get("engine_id") != "native-json-parser"
        or locator.get("engine_version") != "1"
        or origin.origin_type != "DOCUMENT_EVIDENCE"
        or origin.document_id != document.id
        or origin.source_ref != f"sha256:{document.file_hash}"
        or origin.source_availability != "available"
        or origin.locator_status != "present"
        or origin.locator_type != "JSON_POINTER"
        or origin.engine_id != "native-json-parser"
        or origin.engine_version != "1"
    ):
        return None
    try:
        origin_locator = json.loads(origin.locator_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(origin_locator, dict) or origin_locator.get("pointer") != pointer:
        return None
    return fact


def _document_total(document: Document) -> Decimal:
    return _money(sum((abs(_decimal(line.line_total)) for line in document.lines), Decimal("0")))


def _supporting_facts(
    db: Session,
    *,
    chain: OperationChain,
    case: DiscrepancyCase,
) -> list[ProvenanceFact]:
    documents = _role_documents(db, chain)
    invoices = documents["invoice"]
    payments = documents["payment"]
    if not invoices or not payments:
        return []

    facts: list[ProvenanceFact] = []
    for document in [*invoices, *payments]:
        if not document.lines:
            return []
        for line in sorted(document.lines, key=lambda item: item.id):
            fact = _direct_line_total_fact(db, chain=chain, document=document, line=line)
            if fact is None:
                return []
            facts.append(fact)

    invoice_total = sum((_document_total(document) for document in invoices), Decimal("0"))
    payment_total = sum((_document_total(document) for document in payments), Decimal("0"))
    if payment_total <= invoice_total + _THRESHOLD:
        return []
    if _decimal(case.amount_estimate) != _money(payment_total - invoice_total):
        return []
    if len({fact.id for fact in facts}) != len(facts):
        return []
    return sorted(facts, key=lambda fact: fact.fact_key)


def payment_over_invoice_finding_matches_current_support(
    db: Session,
    *,
    finding: ProvenanceFinding,
) -> bool:
    if (
        finding.rule_id != _RULE_ID
        or finding.rule_version != _RULE_VERSION
        or finding.rule_configuration_hash != _RULE_CONFIGURATION_HASH
    ):
        return False
    case = db.get(DiscrepancyCase, finding.case_id)
    if case is None or case.tenant_id != finding.tenant_id or case.case_type != "payment_over_invoice":
        return False
    chain = db.get(OperationChain, case.chain_id)
    if chain is None or chain.tenant_id != finding.tenant_id:
        return False
    expected_fingerprint = hashlib.sha256(f"{chain.id}|payment_over_invoice|payment-over-invoice".encode()).hexdigest()
    if case.fingerprint != expected_fingerprint:
        return False
    current_facts = _supporting_facts(db, chain=chain, case=case)
    if not current_facts:
        return False
    linked_ids = set(
        db.scalars(
            select(ProvenanceFindingFact.fact_id).where(
                ProvenanceFindingFact.tenant_id == finding.tenant_id,
                ProvenanceFindingFact.finding_id == finding.id,
            )
        )
    )
    return len(linked_ids) == len(current_facts) and linked_ids == {fact.id for fact in current_facts}


def record_payment_over_invoice_finding_provenance(
    db: Session,
    *,
    chain: OperationChain,
    case: DiscrepancyCase,
    finding_case_type: str,
    finding_key: str,
) -> None:
    if finding_case_type != "payment_over_invoice" or finding_key != "payment-over-invoice":
        return
    expected_fingerprint = hashlib.sha256(f"{chain.id}|payment_over_invoice|payment-over-invoice".encode()).hexdigest()
    if case.fingerprint != expected_fingerprint:
        return
    facts = _supporting_facts(db, chain=chain, case=case)
    if not facts:
        return
    fact_ids = [fact.id for fact in facts]
    current = db.scalar(
        select(ProvenanceFinding)
        .where(
            ProvenanceFinding.tenant_id == chain.tenant_id,
            ProvenanceFinding.case_id == case.id,
        )
        .order_by(ProvenanceFinding.version.desc())
        .limit(1)
    )
    if current is not None:
        linked_ids = set(
            db.scalars(
                select(ProvenanceFindingFact.fact_id).where(
                    ProvenanceFindingFact.tenant_id == chain.tenant_id,
                    ProvenanceFindingFact.finding_id == current.id,
                )
            )
        )
        if (
            current.rule_id == _RULE_ID
            and current.rule_version == _RULE_VERSION
            and current.rule_configuration_hash == _RULE_CONFIGURATION_HASH
            and linked_ids == set(fact_ids)
        ):
            return
    record_finding(
        db,
        tenant_id=chain.tenant_id,
        case_id=case.id,
        input_fact_ids=fact_ids,
        rule_id=_RULE_ID,
        rule_version=_RULE_VERSION,
        rule_configuration_hash=_RULE_CONFIGURATION_HASH,
        supersedes_finding_id=current.id if current is not None else None,
    )
