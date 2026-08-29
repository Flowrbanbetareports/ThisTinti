from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import ChainDocument, DiscrepancyCase, Document, OperationChain, utcnow
from ..provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceOrigin
from .numeric_fields import all_numeric_available
from .provenance import append_fact, create_origin, record_finding


_RULE_ID = "builtin:payment_without_invoice"
_RULE_VERSION = "1"
_MATCHER_ID = "builtin:operation_chain_matching"
_MATCHER_VERSION = "1"
_MATCHER_CONFIGURATION = {
    "candidate_reference_priority": ["order_numbers", "invoice_numbers", "delivery_numbers"],
    "explicit_reference": "same_tenant_same_supplier_normalized_document_number_or_existing_reference_key",
    "fallback": "same_supplier_open_chain_line_overlap",
    "fuzzy_line_threshold": "0.90",
    "recent_date_bonus": {"days_lte": 60, "bonus": "0.08"},
    "stale_date_penalty": {"days_gt": 180, "penalty": "0.20"},
    "auto_link_threshold": "0.68",
    "auto_link_margin": "0.12",
}
_MATCHER_CONFIGURATION_HASH = hashlib.sha256(
    json.dumps(_MATCHER_CONFIGURATION, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
_RULE_CONFIGURATION = {
    "scope": "exact_current_operation_chain_membership_snapshot",
    "predicate": "active_parsed_payments_present_and_invoice_role_empty",
    "accepted_payment_parse_statuses": ["parsed"],
    "accepted_payment_archived_states": [False],
    "absence_claim": "no_invoice_linked_in_this_exact_snapshot_not_global_nonexistence",
    "amount": "known_payment_total_or_zero_when_numeric_inputs_unavailable",
    "matching_engine_id": _MATCHER_ID,
    "matching_engine_version": _MATCHER_VERSION,
    "matching_configuration_hash": _MATCHER_CONFIGURATION_HASH,
}
_RULE_CONFIGURATION_HASH = hashlib.sha256(
    json.dumps(_RULE_CONFIGURATION, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
_SNAPSHOT_CONFIGURATION_HASH = hashlib.sha256(
    json.dumps(
        {
            "schema": "payment-without-invoice-snapshot/v1",
            "matcher": _MATCHER_CONFIGURATION_HASH,
            "rule": _RULE_CONFIGURATION_HASH,
            "membership": "all_chain_roles_with_match_reason_confidence_document_hash_parse_and_archive_state",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
_MONEY_QUANTUM = Decimal("0.01")
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


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _document_total(document: Document) -> Decimal | None:
    if not all_numeric_available(document.lines, "line_total"):
        return None
    return _money(sum((abs(_decimal(line.line_total)) for line in document.lines), Decimal("0")))


def _current_membership_snapshot(db: Session, chain: OperationChain) -> dict[str, object] | None:
    links = list(
        db.scalars(
            select(ChainDocument)
            .where(
                ChainDocument.tenant_id == chain.tenant_id,
                ChainDocument.chain_id == chain.id,
            )
            .order_by(ChainDocument.role, ChainDocument.sequence_no, ChainDocument.document_id)
        )
    )
    by_role: dict[str, list[ChainDocument]] = defaultdict(list)
    for link in links:
        by_role[link.role].append(link)

    membership: list[dict[str, object]] = []
    document_ids: list[str] = []
    role_document_ids: dict[str, list[str]] = {role: [] for role in _CHAIN_ROLES}
    for role in _CHAIN_ROLES:
        role_links = by_role.get(role, [])
        if role_links:
            for link in role_links:
                role_document_ids[role].append(link.document_id)
                document_ids.append(link.document_id)
                membership.append(
                    {
                        "role": role,
                        "document_id": link.document_id,
                        "sequence_no": int(link.sequence_no),
                        "membership_source": "chain_document",
                        "match_confidence": format(float(link.match_confidence), ".6f"),
                        "match_reason": link.match_reason,
                    }
                )
            continue
        primary_id = getattr(chain, f"{role}_document_id", None)
        if primary_id:
            role_document_ids[role].append(primary_id)
            document_ids.append(primary_id)
            membership.append(
                {
                    "role": role,
                    "document_id": primary_id,
                    "sequence_no": 1,
                    "membership_source": "primary_fallback",
                    "match_confidence": None,
                    "match_reason": "legacy_primary_fallback",
                }
            )

    if len(set(document_ids)) != len(document_ids):
        return None
    documents = (
        list(
            db.scalars(
                select(Document)
                .options(selectinload(Document.lines))
                .where(
                    Document.tenant_id == chain.tenant_id,
                    Document.id.in_(document_ids),
                )
            )
        )
        if document_ids
        else []
    )
    by_id = {document.id: document for document in documents}
    if set(by_id) != set(document_ids):
        return None

    for entry in membership:
        document_id = entry["document_id"]
        if not isinstance(document_id, str):
            return None
        document = by_id[document_id]
        entry["document_type"] = document.document_type
        entry["file_hash"] = document.file_hash
        entry["parse_status"] = document.parse_status
        entry["archived"] = bool(document.archived)

    payment_documents = [by_id[document_id] for document_id in role_document_ids["payment"]]
    invoice_ids = role_document_ids["invoice"]
    payment_ids = role_document_ids["payment"]
    totals = [_document_total(document) for document in payment_documents]
    payment_total = (
        sum((total for total in totals if total is not None), Decimal("0"))
        if all(total is not None for total in totals)
        else None
    )
    expected_amount = _money(payment_total) if payment_total is not None else Decimal("0.00")

    return {
        "schema": "payment-without-invoice-snapshot/v1",
        "chain_id": chain.id,
        "tenant_id": chain.tenant_id,
        "claim_boundary": "no invoice is linked in this exact operation-chain snapshot; this does not assert global invoice nonexistence",
        "matcher": {
            "id": _MATCHER_ID,
            "version": _MATCHER_VERSION,
            "configuration_hash": _MATCHER_CONFIGURATION_HASH,
        },
        "rule": {
            "id": _RULE_ID,
            "version": _RULE_VERSION,
            "configuration_hash": _RULE_CONFIGURATION_HASH,
        },
        "membership": membership,
        "primary_document_ids": {role: getattr(chain, f"{role}_document_id", None) for role in _CHAIN_ROLES},
        "invoice_document_ids": invoice_ids,
        "payment_document_ids": payment_ids,
        "predicate": {
            "payments_present": bool(payment_ids),
            "invoice_role_empty": not invoice_ids,
        },
        "payment_total": {
            "status": "known" if payment_total is not None else "numeric_inputs_unavailable",
            "value": format(payment_total, ".2f") if payment_total is not None else None,
            "case_amount_estimate": format(expected_amount, ".2f"),
        },
    }


def _snapshot_is_eligible(snapshot: dict[str, object]) -> bool:
    predicate = snapshot.get("predicate")
    membership = snapshot.get("membership")
    payment_entries = (
        [entry for entry in membership if isinstance(entry, dict) and entry.get("role") == "payment"]
        if isinstance(membership, list)
        else []
    )
    return (
        isinstance(predicate, dict)
        and predicate.get("payments_present") is True
        and predicate.get("invoice_role_empty") is True
        and bool(payment_entries)
        and all(
            entry.get("parse_status") == "parsed" and entry.get("archived") is False
            for entry in payment_entries
        )
    )


def _latest_snapshot_fact(db: Session, chain: OperationChain) -> ProvenanceFact | None:
    return db.scalar(
        select(ProvenanceFact)
        .where(
            ProvenanceFact.tenant_id == chain.tenant_id,
            ProvenanceFact.fact_key == f"operation_chain:{chain.id}:payment_without_invoice_snapshot",
        )
        .order_by(ProvenanceFact.version.desc())
        .limit(1)
    )


def _origin_matches_snapshot(db: Session, fact: ProvenanceFact, value_json: str) -> bool:
    origin = db.get(ProvenanceOrigin, fact.origin_id)
    expected_source_ref = f"sha256:{hashlib.sha256(value_json.encode('utf-8')).hexdigest()}"
    return bool(
        origin is not None
        and origin.tenant_id == fact.tenant_id
        and origin.origin_type == "SYSTEM_OBSERVATION"
        and origin.source_ref == expected_source_ref
        and origin.engine_id == _MATCHER_ID
        and origin.engine_version == _MATCHER_VERSION
        and origin.configuration_hash == _SNAPSHOT_CONFIGURATION_HASH
        and origin.observed_at is not None
    )


def _ensure_snapshot_fact(
    db: Session,
    *,
    chain: OperationChain,
    snapshot: dict[str, object],
) -> ProvenanceFact:
    value_json = _canonical_json(snapshot)
    current = _latest_snapshot_fact(db, chain)
    if (
        current is not None
        and current.fact_type == "operation_chain.payment_without_invoice_snapshot"
        and current.value_json == value_json
        and _origin_matches_snapshot(db, current, value_json)
    ):
        return current

    source_ref = f"sha256:{hashlib.sha256(value_json.encode('utf-8')).hexdigest()}"
    origin = create_origin(
        db,
        tenant_id=chain.tenant_id,
        origin_type="SYSTEM_OBSERVATION",
        source_ref=source_ref,
        observed_at=utcnow(),
        engine_id=_MATCHER_ID,
        engine_version=_MATCHER_VERSION,
        configuration_hash=_SNAPSHOT_CONFIGURATION_HASH,
    )
    return append_fact(
        db,
        tenant_id=chain.tenant_id,
        fact_key=f"operation_chain:{chain.id}:payment_without_invoice_snapshot",
        fact_type="operation_chain.payment_without_invoice_snapshot",
        value_json=value_json,
        origin_id=origin.id,
        supersedes_fact_id=current.id if current is not None else None,
    )


def _case_matches_snapshot(case: DiscrepancyCase, snapshot: dict[str, object]) -> bool:
    payment_total = snapshot.get("payment_total")
    if not isinstance(payment_total, dict):
        return False
    expected = payment_total.get("case_amount_estimate")
    try:
        return expected is not None and _money(_decimal(case.amount_estimate)) == Decimal(str(expected))
    except (ArithmeticError, TypeError, ValueError):
        return False


def payment_without_invoice_finding_matches_current_support(
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
    if case is None or case.tenant_id != finding.tenant_id or case.case_type != "payment_without_invoice":
        return False
    chain = db.get(OperationChain, case.chain_id)
    if chain is None or chain.tenant_id != finding.tenant_id:
        return False
    expected_fingerprint = hashlib.sha256(
        f"{chain.id}|payment_without_invoice|payment-without-invoice".encode()
    ).hexdigest()
    if case.fingerprint != expected_fingerprint:
        return False

    snapshot = _current_membership_snapshot(db, chain)
    if snapshot is None or not _snapshot_is_eligible(snapshot) or not _case_matches_snapshot(case, snapshot):
        return False
    current = _latest_snapshot_fact(db, chain)
    if current is None:
        return False
    expected_value = _canonical_json(snapshot)
    if (
        current.fact_type != "operation_chain.payment_without_invoice_snapshot"
        or current.value_json != expected_value
        or not _origin_matches_snapshot(db, current, expected_value)
    ):
        return False
    linked_ids = set(
        db.scalars(
            select(ProvenanceFindingFact.fact_id).where(
                ProvenanceFindingFact.tenant_id == finding.tenant_id,
                ProvenanceFindingFact.finding_id == finding.id,
            )
        )
    )
    return linked_ids == {current.id}


def record_payment_without_invoice_finding_provenance(
    db: Session,
    *,
    chain: OperationChain,
    case: DiscrepancyCase,
    finding_case_type: str,
    finding_key: str,
) -> None:
    if finding_case_type != "payment_without_invoice" or finding_key != "payment-without-invoice":
        return
    expected_fingerprint = hashlib.sha256(
        f"{chain.id}|payment_without_invoice|payment-without-invoice".encode()
    ).hexdigest()
    if case.fingerprint != expected_fingerprint:
        return
    snapshot = _current_membership_snapshot(db, chain)
    if snapshot is None or not _snapshot_is_eligible(snapshot) or not _case_matches_snapshot(case, snapshot):
        return
    fact = _ensure_snapshot_fact(db, chain=chain, snapshot=snapshot)
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
            and linked_ids == {fact.id}
        ):
            return
    record_finding(
        db,
        tenant_id=chain.tenant_id,
        case_id=case.id,
        input_fact_ids=[fact.id],
        rule_id=_RULE_ID,
        rule_version=_RULE_VERSION,
        rule_configuration_hash=_RULE_CONFIGURATION_HASH,
        supersedes_finding_id=current.id if current is not None else None,
    )
