from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import ChainDocument, DiscrepancyCase, Document, DocumentLine, OperationChain
from ..provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceOrigin
from .line_matching import group_chain_lines
from .provenance import record_finding
from .units import canonical_unit_price, profiles_compatible, quantity_profile

_RULE_ID = "builtin:invoiced_over_received"
_RULE_VERSION = "1"
_RULE_CONFIGURATION_HASH = hashlib.sha256(
    json.dumps(
        {
            "commercial_role_priority": ["confirmation", "order", "proposal"],
            "reference": "delivery_for_matching_line_else_commercial",
            "comparison": "canonical_invoice_quantity_gt_canonical_reference_quantity_plus_0.000001",
            "amount": "excess_canonical_quantity_times_weighted_canonical_invoice_unit_price",
            "support": (
                "all_current_reference_quantity,uom and invoice_quantity,uom,unit_price,price_base_quantity "
                "must be direct native JSON evidence"
            ),
            "missing_or_defaulted_inputs": "fail_closed",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
_QTY_EPSILON = Decimal("0.000001")
_MONEY_QUANTUM = Decimal("0.01")
_ROLES = ("proposal", "order", "confirmation", "delivery", "invoice")
_NUMERIC_FIELDS = {"quantity", "unit_price", "price_base_quantity"}
_REQUIRED_REFERENCE_FIELDS = ("quantity", "unit_of_measure")
_REQUIRED_INVOICE_FIELDS = ("quantity", "unit_of_measure", "unit_price", "price_base_quantity")
_FACT_TYPES = {
    "quantity": "document_line.quantity",
    "unit_of_measure": "document_line.unit_of_measure",
    "unit_price": "document_line.unit_price",
    "price_base_quantity": "document_line.price_base_quantity",
}
_POINTER_FIELDS = {
    "quantity": {"quantity"},
    "unit_of_measure": {"unit_of_measure", "uom"},
    "unit_price": {"unit_price"},
    "price_base_quantity": {"price_base_quantity"},
}


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
    linked_by_role: dict[str, list[str]] = defaultdict(list)
    for role, document_id, _sequence_no in links:
        linked_by_role[role].append(document_id)

    ids: list[str] = []
    role_ids: dict[str, list[str]] = {}
    for role in _ROLES:
        current = linked_by_role.get(role, [])
        if not current:
            primary_id = getattr(chain, f"{role}_document_id", None)
            current = [primary_id] if primary_id else []
        role_ids[role] = current
        ids.extend(current)
    if not ids:
        return {role: [] for role in _ROLES}

    documents = list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.lines))
            .where(
                Document.tenant_id == chain.tenant_id,
                Document.id.in_(set(ids)),
            )
        )
    )
    by_id = {document.id: document for document in documents}
    return {role: [by_id[document_id] for document_id in role_ids[role] if document_id in by_id] for role in _ROLES}


def _reference_and_invoice_lines(
    db: Session,
    *,
    chain: OperationChain,
    finding_key: str,
) -> tuple[list[DocumentLine], list[DocumentLine]] | None:
    documents = _role_documents(db, chain)
    commercial_role = "confirmation" if documents["confirmation"] else "order" if documents["order"] else "proposal"
    if not documents["invoice"]:
        return None
    grouped = group_chain_lines(db, chain, documents)
    invoices = grouped["invoice"].get(finding_key, [])
    deliveries = grouped["delivery"].get(finding_key, [])
    commercial = grouped[commercial_role].get(finding_key, []) if documents[commercial_role] else []
    reference = deliveries if deliveries else commercial
    if not invoices or not reference:
        return None

    invoice_profile = quantity_profile(invoices)
    reference_profile = quantity_profile(reference)
    if not profiles_compatible(invoice_profile, reference_profile):
        return None
    if invoice_profile.quantity <= reference_profile.quantity + _QTY_EPSILON:
        return None
    return reference, invoices


def _finding_key_for_case(db: Session, *, chain: OperationChain, case: DiscrepancyCase) -> str | None:
    documents = _role_documents(db, chain)
    commercial_role = "confirmation" if documents["confirmation"] else "order" if documents["order"] else "proposal"
    if not documents["invoice"]:
        return None
    grouped = group_chain_lines(db, chain, documents)
    keys = set(grouped[commercial_role]) | set(grouped["delivery"]) | set(grouped["invoice"])
    matches: list[str] = []
    for key in sorted(keys):
        invoices = grouped["invoice"].get(key, [])
        deliveries = grouped["delivery"].get(key, [])
        commercial = grouped[commercial_role].get(key, []) if documents[commercial_role] else []
        reference = deliveries if deliveries else commercial
        if not invoices or not reference:
            continue
        invoice_profile = quantity_profile(invoices)
        reference_profile = quantity_profile(reference)
        if not profiles_compatible(invoice_profile, reference_profile):
            continue
        if invoice_profile.quantity <= reference_profile.quantity + _QTY_EPSILON:
            continue
        fingerprint = hashlib.sha256(f"{chain.id}|invoiced_over_received|{key}".encode()).hexdigest()
        if fingerprint == case.fingerprint:
            matches.append(key)
    return matches[0] if len(matches) == 1 else None


def _raw_locator(line: DocumentLine, field_name: str) -> dict[str, object] | None:
    try:
        raw = json.loads(line.raw_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    locators = raw.get("_source_locators")
    if not isinstance(locators, dict):
        return None
    locator = locators.get(field_name)
    return locator if isinstance(locator, dict) else None


def _fact_value_matches(fact: ProvenanceFact, line: DocumentLine, field_name: str) -> bool:
    try:
        value = json.loads(fact.value_json)
    except (TypeError, json.JSONDecodeError):
        return False
    if field_name in _NUMERIC_FIELDS:
        try:
            return Decimal(str(value)) == _decimal(getattr(line, field_name))
        except (InvalidOperation, TypeError, ValueError):
            return False
    expected = getattr(line, field_name)
    return isinstance(value, str) and expected is not None and value == str(expected)


def _direct_fact(
    db: Session,
    *,
    chain: OperationChain,
    line: DocumentLine,
    document: Document,
    field_name: str,
) -> ProvenanceFact | None:
    fact_key = f"document_line:{line.id}:{field_name}"
    fact = db.scalar(
        select(ProvenanceFact)
        .where(
            ProvenanceFact.tenant_id == chain.tenant_id,
            ProvenanceFact.fact_key == fact_key,
        )
        .order_by(ProvenanceFact.version.desc())
        .limit(1)
    )
    if fact is None or fact.fact_type != _FACT_TYPES[field_name] or not _fact_value_matches(fact, line, field_name):
        return None
    origin = db.get(ProvenanceOrigin, fact.origin_id)
    locator = _raw_locator(line, field_name)
    if origin is None or locator is None:
        return None
    pointer = str(locator.get("pointer") or "")
    parts = pointer.split("/")
    if (
        len(parts) != 4
        or parts[0] != ""
        or parts[1] != "lines"
        or not parts[2].isdigit()
        or parts[3] not in _POINTER_FIELDS[field_name]
    ):
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


def _weighted_invoice_price(lines: list[DocumentLine]) -> Decimal:
    weighted: list[tuple[Decimal, Decimal]] = []
    for line in lines:
        profile = quantity_profile([line])
        if not profile.compatible:
            return Decimal("0")
        quantity = abs(profile.quantity)
        weighted.append(
            (quantity, canonical_unit_price(line.unit_price, line.price_base_quantity, line.unit_of_measure))
        )
    total_quantity = sum((quantity for quantity, _price in weighted), Decimal("0"))
    if not total_quantity:
        return Decimal("0")
    return sum((quantity * price for quantity, price in weighted), Decimal("0")) / total_quantity


def _supporting_facts(
    db: Session,
    *,
    chain: OperationChain,
    case: DiscrepancyCase,
    finding_key: str,
) -> list[ProvenanceFact]:
    lines = _reference_and_invoice_lines(db, chain=chain, finding_key=finding_key)
    if lines is None:
        return []
    reference, invoices = lines
    document_ids = {line.document_id for line in [*reference, *invoices]}
    documents = {
        document.id: document
        for document in db.scalars(
            select(Document).where(
                Document.tenant_id == chain.tenant_id,
                Document.id.in_(document_ids),
            )
        )
    }
    if set(documents) != document_ids:
        return []

    facts: list[ProvenanceFact] = []
    for line in sorted(reference, key=lambda item: item.id):
        document = documents[line.document_id]
        for field_name in _REQUIRED_REFERENCE_FIELDS:
            fact = _direct_fact(db, chain=chain, line=line, document=document, field_name=field_name)
            if fact is None:
                return []
            facts.append(fact)
    for line in sorted(invoices, key=lambda item: item.id):
        document = documents[line.document_id]
        for field_name in _REQUIRED_INVOICE_FIELDS:
            fact = _direct_fact(db, chain=chain, line=line, document=document, field_name=field_name)
            if fact is None:
                return []
            facts.append(fact)

    reference_profile = quantity_profile(reference)
    invoice_profile = quantity_profile(invoices)
    expected_amount = _money(
        (invoice_profile.quantity - reference_profile.quantity) * _weighted_invoice_price(invoices)
    )
    if _decimal(case.amount_estimate) != expected_amount:
        return []
    if len({fact.id for fact in facts}) != len(facts):
        return []
    return sorted(facts, key=lambda fact: fact.fact_key)


def invoiced_over_received_finding_matches_current_support(
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
    if case is None or case.tenant_id != finding.tenant_id or case.case_type != "invoiced_over_received":
        return False
    chain = db.get(OperationChain, case.chain_id)
    if chain is None or chain.tenant_id != finding.tenant_id:
        return False
    finding_key = _finding_key_for_case(db, chain=chain, case=case)
    if finding_key is None:
        return False
    current_facts = _supporting_facts(db, chain=chain, case=case, finding_key=finding_key)
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


def record_invoiced_over_received_finding_provenance(
    db: Session,
    *,
    chain: OperationChain,
    case: DiscrepancyCase,
    finding_case_type: str,
    finding_key: str,
) -> None:
    if finding_case_type != "invoiced_over_received":
        return
    facts = _supporting_facts(db, chain=chain, case=case, finding_key=finding_key)
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
