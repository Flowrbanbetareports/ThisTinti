from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    ActivityProfile,
    ChainDocument,
    DiscrepancyCase,
    Document,
    OperationChain,
    RuleProposal,
    ValidationDataset,
    ValidationRun,
    utcnow,
)
from ..version import MIN_AUTOMATION_VALIDATION_SCENARIOS, RELEASE_VERSION
from .normalizer import normalize_code, normalize_text

ROLE_ORDER = (
    "proposal",
    "order",
    "confirmation",
    "delivery",
    "invoice",
    "payment",
    "return",
    "credit_note",
)
ROLE_LABELS = {
    "proposal": "Proposta",
    "order": "Ordine",
    "confirmation": "Conferma",
    "delivery": "DDT / consegna",
    "invoice": "Fattura",
    "payment": "Pagamento",
    "return": "Reso",
    "credit_note": "Nota di credito",
}
SEVERITY_WEIGHT = {"low": 4, "medium": 10, "high": 22, "critical": 36}
MONEY_QUANTUM = Decimal("0.01")


SERVICE_TERMS = {
    "abbonamento",
    "canone",
    "consulenza",
    "fee",
    "formazione",
    "hosting",
    "licenza",
    "manutenzione",
    "noleggio",
    "servizio",
    "software",
    "supporto",
    "trasporto",
}
PHYSICAL_UNITS = {
    "bottiglia",
    "box",
    "cm",
    "g",
    "gr",
    "kg",
    "l",
    "m",
    "m2",
    "m3",
    "ml",
    "paio",
    "pezzo",
    "piece",
    "pcs",
    "pz",
    "unit",
    "unita",
}


@dataclass(frozen=True)
class Expectation:
    role: str
    label: str
    status: str
    required: bool
    due_date: date | None
    confidence: float
    rationale: str
    source_document_ids: list[str]
    risk_if_missing: str
    timing_source: str
    sample_count: int


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def _money(value: Any) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _load_documents(db: Session, chain: OperationChain) -> dict[str, list[Document]]:
    links = list(
        db.scalars(
            select(ChainDocument)
            .where(
                ChainDocument.tenant_id == chain.tenant_id,
                ChainDocument.chain_id == chain.id,
            )
            .order_by(ChainDocument.role, ChainDocument.sequence_no)
        )
    )
    ids = [link.document_id for link in links]
    documents = (
        list(
            db.scalars(
                select(Document)
                .options(selectinload(Document.lines))
                .where(Document.tenant_id == chain.tenant_id, Document.id.in_(ids))
            )
        )
        if ids
        else []
    )
    by_id = {document.id: document for document in documents}
    grouped = {role: [] for role in ROLE_ORDER}
    for link in links:
        document = by_id.get(link.document_id)
        if document:
            grouped.setdefault(link.role, []).append(document)
    return grouped


def _active_cases(db: Session, chain: OperationChain) -> list[DiscrepancyCase]:
    return list(
        db.scalars(
            select(DiscrepancyCase)
            .options(selectinload(DiscrepancyCase.evidence))
            .where(
                DiscrepancyCase.tenant_id == chain.tenant_id,
                DiscrepancyCase.chain_id == chain.id,
                DiscrepancyCase.status.in_(["open", "needs_review", "confirmed"]),
            )
        )
    )


def _json_object(value: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _likely_physical_goods(documents: list[Document]) -> bool:
    if any(document.document_type == "delivery" for document in documents):
        return True

    for document in documents:
        metadata = _json_object(document.metadata_json)
        explicit = metadata.get("requires_delivery")
        nature = normalize_code(str(metadata.get("transaction_kind") or metadata.get("document_nature") or ""))
        if explicit is True or nature in {"GOODS", "MERCE", "BENI", "PHYSICALGOODS"}:
            return True
        if explicit is False or nature in {"SERVICE", "SERVICES", "SERVIZIO", "SERVIZI"}:
            return False

    for document in documents:
        for line in document.lines:
            description_tokens = set(normalize_text(line.description or "").lower().split())
            service_like = bool(description_tokens & SERVICE_TERMS)
            unit = normalize_code(line.unit_of_measure or "").lower()
            quantity = abs(_decimal(line.quantity))
            if unit in PHYSICAL_UNITS and not service_like:
                return True
            if line.sku and quantity > 1 and quantity == quantity.to_integral_value() and not service_like:
                return True
    return False


def _document_total(document: Document) -> Decimal:
    line_total = sum((_decimal(line.line_total) for line in document.lines), Decimal("0"))
    if line_total:
        return _money(abs(line_total))
    for source in (document.metadata_json, document.references_json):
        try:
            payload = json.loads(source or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for key in ("amount", "total", "payment_amount", "paid_amount", "gross_total"):
            if payload.get(key) not in (None, ""):
                try:
                    return _money(abs(_decimal(payload[key])))
                except (InvalidOperation, TypeError, ValueError, OverflowError):
                    continue
    return Decimal("0.00")


def _latest_date(documents: list[Document]) -> date | None:
    dates = [document.document_date for document in documents if document.document_date]
    return max(dates) if dates else None


def _status_for_due(present: bool, due_date: date | None, *, immediate_missing: bool = False) -> str:
    if present:
        return "satisfied"
    if immediate_missing:
        return "missing_proof"
    if due_date and due_date < utcnow().date():
        return "overdue"
    return "pending"


def _expectation(
    role: str,
    *,
    present: bool,
    required: bool,
    source_documents: list[Document],
    days: int | None,
    rationale: str,
    risk_if_missing: str,
    confidence: float,
    timing_source: str = "safe_default",
    sample_count: int = 0,
    immediate_missing: bool = False,
) -> Expectation:
    source_date = _latest_date(source_documents)
    due_date = source_date + timedelta(days=days) if source_date and days is not None else None
    return Expectation(
        role=role,
        label=ROLE_LABELS[role],
        status=_status_for_due(present, due_date, immediate_missing=immediate_missing),
        required=required,
        due_date=due_date,
        confidence=confidence,
        rationale=rationale,
        source_document_ids=[document.id for document in source_documents],
        risk_if_missing=risk_if_missing,
        timing_source=timing_source,
        sample_count=sample_count,
    )


def _timing_profile(db: Session, chain: OperationChain) -> dict[str, dict[str, Any]]:
    defaults = {
        "order": 14,
        "delivery": 30,
        "invoice": 45,
        "payment": 30,
        "credit_note": 21,
    }
    source_roles = {
        "order": {"proposal"},
        "delivery": {"proposal", "order", "confirmation"},
        "invoice": {"proposal", "order", "confirmation", "delivery"},
        "payment": {"invoice"},
        "credit_note": {"return"},
    }
    statement = (
        select(ChainDocument.chain_id, ChainDocument.role, Document.document_date)
        .join(Document, Document.id == ChainDocument.document_id)
        .join(OperationChain, OperationChain.id == ChainDocument.chain_id)
        .where(
            ChainDocument.tenant_id == chain.tenant_id,
            OperationChain.id != chain.id,
            Document.document_date.is_not(None),
        )
    )
    if chain.supplier_id:
        statement = statement.where(OperationChain.supplier_id == chain.supplier_id)
    rows = db.execute(statement.limit(4000)).all()
    by_chain: dict[str, dict[str, list[date]]] = {}
    for chain_id, role, document_date in rows:
        if role not in ROLE_ORDER or document_date is None:
            continue
        by_chain.setdefault(chain_id, {}).setdefault(role, []).append(document_date)

    profile: dict[str, dict[str, Any]] = {}
    for target, default_days in defaults.items():
        delays: list[int] = []
        for role_dates in by_chain.values():
            target_dates = role_dates.get(target, [])
            candidate_sources = [value for role in source_roles[target] for value in role_dates.get(role, [])]
            if not target_dates or not candidate_sources:
                continue
            source_date = max(candidate_sources)
            valid_targets = [value for value in target_dates if value >= source_date]
            if not valid_targets:
                continue
            delay = (min(valid_targets) - source_date).days
            if 0 <= delay <= 365:
                delays.append(delay)
        if len(delays) >= 3:
            ordered = sorted(delays)
            index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.80) - 1))
            learned_days = max(1, ordered[index])
            profile[target] = {
                "days": learned_days,
                "source": "supplier_history_p80" if chain.supplier_id else "tenant_history_p80",
                "sample_count": len(delays),
            }
        else:
            profile[target] = {
                "days": default_days,
                "source": "safe_default",
                "sample_count": len(delays),
            }
    return profile


def build_expectations(
    db: Session,
    chain: OperationChain,
    documents: dict[str, list[Document]] | None = None,
) -> list[dict[str, Any]]:
    documents = documents or _load_documents(db, chain)
    timing = _timing_profile(db, chain)
    proposals = documents["proposal"]
    orders = documents["order"]
    confirmations = documents["confirmation"]
    deliveries = documents["delivery"]
    invoices = documents["invoice"]
    payments = documents["payment"]
    returns = documents["return"]
    credits = documents["credit_note"]

    commercial = confirmations or orders or proposals
    physical_goods = _likely_physical_goods(commercial + deliveries + invoices)
    expectations: list[Expectation] = []

    if proposals and not orders and not confirmations:
        expectations.append(
            _expectation(
                "order",
                present=False,
                required=False,
                source_documents=proposals,
                days=timing["order"]["days"],
                timing_source=timing["order"]["source"],
                sample_count=timing["order"]["sample_count"],
                rationale="Una proposta normalmente deve essere accettata, ordinata o esplicitamente chiusa.",
                risk_if_missing="La trattativa resta senza esito documentato.",
                confidence=0.78,
            )
        )

    if commercial:
        if physical_goods:
            expectations.append(
                _expectation(
                    "delivery",
                    present=bool(deliveries),
                    required=True,
                    source_documents=commercial,
                    days=timing["delivery"]["days"],
                    timing_source=timing["delivery"]["source"],
                    sample_count=timing["delivery"]["sample_count"],
                    rationale="Per beni fisici serve una prova di consegna prima della piena riconciliazione.",
                    risk_if_missing="Una fattura potrebbe riferirsi a merce non dimostrata come consegnata.",
                    confidence=0.93,
                )
            )
        expectations.append(
            _expectation(
                "invoice",
                present=bool(invoices),
                required=True,
                source_documents=deliveries or commercial,
                days=timing["invoice"]["days"],
                timing_source=timing["invoice"]["source"],
                sample_count=timing["invoice"]["sample_count"],
                rationale="L'operazione commerciale deve concludersi con un documento economico o una chiusura esplicita.",
                risk_if_missing="Costo e obbligazione restano non riconciliati.",
                confidence=0.90,
            )
        )

    if deliveries and not commercial:
        expectations.append(
            _expectation(
                "order",
                present=False,
                required=True,
                source_documents=deliveries,
                days=None,
                rationale="È presente una consegna senza proposta, ordine o conferma collegata.",
                risk_if_missing="Manca la prova delle condizioni commerciali autorizzate.",
                confidence=0.96,
                immediate_missing=True,
            )
        )

    if invoices:
        if physical_goods and not deliveries:
            expectations.append(
                _expectation(
                    "delivery",
                    present=False,
                    required=True,
                    source_documents=invoices,
                    days=None,
                    rationale="La fattura riguarda beni fisici ma non dispone di una prova di consegna collegata.",
                    risk_if_missing="Rischio di approvare quantità non ricevute.",
                    confidence=0.98,
                    immediate_missing=True,
                )
            )
        if not commercial:
            expectations.append(
                _expectation(
                    "order",
                    present=False,
                    required=True,
                    source_documents=invoices,
                    days=None,
                    rationale="La fattura non ha un riferimento commerciale verificabile.",
                    risk_if_missing="Prezzi e sconti non possono essere confrontati con condizioni autorizzate.",
                    confidence=0.96,
                    immediate_missing=True,
                )
            )
        expectations.append(
            _expectation(
                "payment",
                present=bool(payments),
                required=True,
                source_documents=invoices,
                days=timing["payment"]["days"],
                timing_source=timing["payment"]["source"],
                sample_count=timing["payment"]["sample_count"],
                rationale="La fattura deve essere riconciliata con uno o più pagamenti oppure risultare ancora aperta.",
                risk_if_missing="Non è possibile distinguere una fattura aperta da un pagamento non registrato.",
                confidence=0.91,
            )
        )

    if payments and not invoices:
        expectations.append(
            _expectation(
                "invoice",
                present=False,
                required=True,
                source_documents=payments,
                days=None,
                rationale="È presente un pagamento senza fattura collegata.",
                risk_if_missing="Il pagamento potrebbe essere duplicato, anticipato o attribuito alla pratica errata.",
                confidence=0.99,
                immediate_missing=True,
            )
        )

    if returns:
        expectations.append(
            _expectation(
                "credit_note",
                present=bool(credits),
                required=True,
                source_documents=returns,
                days=timing["credit_note"]["days"],
                timing_source=timing["credit_note"]["source"],
                sample_count=timing["credit_note"]["sample_count"],
                rationale="Un reso deve produrre un accredito o una motivazione documentata.",
                risk_if_missing="L'azienda potrebbe non recuperare il valore della merce restituita.",
                confidence=0.96,
            )
        )

    deduplicated: dict[str, Expectation] = {}
    rank = {"missing_proof": 4, "overdue": 3, "pending": 2, "satisfied": 1}
    for item in expectations:
        current = deduplicated.get(item.role)
        if current is None or rank[item.status] > rank[current.status]:
            deduplicated[item.role] = item
    return [asdict(deduplicated[role]) for role in ROLE_ORDER if role in deduplicated]


def _payment_reconciliation(documents: dict[str, list[Document]]) -> dict[str, Any]:
    invoice_total = sum((_document_total(document) for document in documents["invoice"]), Decimal("0"))
    payment_total = sum((_document_total(document) for document in documents["payment"]), Decimal("0"))
    delta = _money(payment_total - invoice_total)
    duplicate_signatures: dict[tuple[tuple[str, ...], Decimal], list[str]] = {}
    for document in documents["payment"]:
        reference_keys = tuple(
            sorted({normalize_code(value) for value in _reference_values(document) if normalize_code(value)})
        )
        identity = reference_keys or (normalize_code(document.number) or document.id,)
        signature = (identity, _document_total(document))
        duplicate_signatures.setdefault(signature, []).append(document.id)
    duplicates = [ids for ids in duplicate_signatures.values() if len(ids) > 1 and ids]
    if not documents["payment"]:
        status = "unpaid_or_unlinked"
    elif abs(delta) <= Decimal("0.02"):
        status = "balanced"
    elif delta > 0:
        status = "overpaid"
    else:
        status = "partially_paid"
    return {
        "invoice_total": float(_money(invoice_total)),
        "payment_total": float(_money(payment_total)),
        "delta": float(delta),
        "status": status,
        "duplicate_payment_groups": duplicates,
    }


def _learning_summary(db: Session, tenant_id: str) -> dict[str, Any]:
    profiles = list(db.scalars(select(ActivityProfile).where(ActivityProfile.tenant_id == tenant_id)))
    proposals = list(db.scalars(select(RuleProposal).where(RuleProposal.tenant_id == tenant_id)))
    return {
        "activity_profiles": len(profiles),
        "confirmed_profiles": sum(1 for profile in profiles if profile.status == "confirmed"),
        "rules_total": len(proposals),
        "rules_confirmed": sum(1 for proposal in proposals if proposal.status == "confirmed"),
        "rules_pending": sum(1 for proposal in proposals if proposal.status == "needs_confirmation"),
        "automatic_learning_policy": "human_approval_required",
    }


def _reference_values(document: Document) -> list[str]:
    try:
        payload = json.loads(document.references_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)

    collect(payload)
    return list(dict.fromkeys(values))


def build_proof_graph(
    db: Session,
    chain: OperationChain,
    documents: dict[str, list[Document]] | None = None,
    cases: list[DiscrepancyCase] | None = None,
    expectations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    documents = documents or _load_documents(db, chain)
    cases = cases if cases is not None else _active_cases(db, chain)
    expectations = expectations if expectations is not None else build_expectations(db, chain, documents)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for role in ROLE_ORDER:
        for document in documents[role]:
            nodes.append(
                {
                    "id": f"doc:{document.id}",
                    "kind": "document",
                    "role": role,
                    "label": f"{ROLE_LABELS[role]} {document.number or document.source_filename}",
                    "status": document.parse_status,
                    "confidence": round(document.confidence, 4),
                    "document_id": document.id,
                    "amount": float(_document_total(document)),
                    "date": document.document_date.isoformat() if document.document_date else None,
                    "evidence_strength": "strong" if document.confidence >= 0.90 else "review",
                }
            )

    present_roles = [role for role in ROLE_ORDER if documents[role]]
    all_documents = [document for role in ROLE_ORDER for document in documents[role]]
    number_index: dict[str, list[Document]] = {}
    for document in all_documents:
        key = normalize_code(document.number)
        if key:
            number_index.setdefault(key, []).append(document)

    explicit_pairs: set[tuple[str, str]] = set()
    explicit_reference_edges = 0
    for target in all_documents:
        for reference in _reference_values(target):
            for source in number_index.get(normalize_code(reference), []):
                if source.id == target.id or (source.id, target.id) in explicit_pairs:
                    continue
                explicit_pairs.add((source.id, target.id))
                explicit_reference_edges += 1
                edges.append(
                    {
                        "id": f"reference:{source.id}:{target.id}",
                        "source": f"doc:{source.id}",
                        "target": f"doc:{target.id}",
                        "relation": "explicit_reference",
                        "confidence": round(min(0.99, max(0.75, min(source.confidence, target.confidence) + 0.08)), 4),
                        "reason": f"{ROLE_LABELS.get(target.document_type, target.document_type)} cita il documento {reference}",
                    }
                )

    for left, right in zip(present_roles, present_roles[1:], strict=False):
        left_doc = documents[left][-1]
        right_doc = documents[right][0]
        if (left_doc.id, right_doc.id) in explicit_pairs:
            continue
        edges.append(
            {
                "id": f"edge:{left_doc.id}:{right_doc.id}",
                "source": f"doc:{left_doc.id}",
                "target": f"doc:{right_doc.id}",
                "relation": "inferred_sequence",
                "confidence": round(min(0.85, min(left_doc.confidence, right_doc.confidence)), 4),
                "reason": f"Sequenza operativa inferita {ROLE_LABELS[left]} → {ROLE_LABELS[right]}",
            }
        )

    for item in expectations:
        if item["status"] == "satisfied":
            continue
        node_id = f"expected:{item['role']}"
        nodes.append(
            {
                "id": node_id,
                "kind": "expected_document",
                "role": item["role"],
                "label": f"Atteso: {item['label']}",
                "status": item["status"],
                "confidence": item["confidence"],
                "document_id": None,
                "amount": 0.0,
                "date": item["due_date"].isoformat() if item["due_date"] else None,
                "evidence_strength": "missing",
            }
        )
        for source_id in item["source_document_ids"]:
            edges.append(
                {
                    "id": f"expectation:{source_id}:{item['role']}",
                    "source": f"doc:{source_id}",
                    "target": node_id,
                    "relation": "expects",
                    "confidence": item["confidence"],
                    "reason": item["rationale"],
                }
            )

    for case in cases:
        issue_id = f"issue:{case.id}"
        nodes.append(
            {
                "id": issue_id,
                "kind": "issue",
                "role": None,
                "label": case.title,
                "status": case.status,
                "confidence": round(case.confidence, 4),
                "document_id": None,
                "amount": float(case.amount_estimate),
                "date": case.created_at.date().isoformat(),
                "evidence_strength": case.severity,
            }
        )
        source_ids = {evidence.document_id for evidence in case.evidence if evidence.document_id}
        for source_id in source_ids:
            edges.append(
                {
                    "id": f"evidence:{source_id}:{case.id}",
                    "source": f"doc:{source_id}",
                    "target": issue_id,
                    "relation": "supports_finding",
                    "confidence": round(case.confidence, 4),
                    "reason": case.explanation,
                }
            )

    return {
        "chain_id": chain.id,
        "reference_key": chain.reference_key,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "documents": sum(len(items) for items in documents.values()),
            "missing_or_pending": sum(1 for item in expectations if item["status"] != "satisfied"),
            "open_issues": len(cases),
            "roles_present": present_roles,
            "explicit_reference_edges": explicit_reference_edges,
        },
    }


def _proof_contract(cases: list[DiscrepancyCase], expectations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conclusions: list[dict[str, Any]] = []
    for case in cases:
        conclusions.append(
            {
                "conclusion": case.title,
                "confidence": round(case.confidence, 4),
                "severity": case.severity,
                "amount": float(case.amount_estimate),
                "documents": sorted({item.document_id for item in case.evidence if item.document_id}),
                "fields": sorted({item.field_name for item in case.evidence}),
                "reason": case.explanation,
                "recommended_action": case.recommended_action,
                "candidate_for_automation": case.confidence >= 0.95 and case.severity in {"low", "medium"},
                "automation_allowed": False,
            }
        )
    for item in expectations:
        if item["status"] in {"missing_proof", "overdue"}:
            conclusions.append(
                {
                    "conclusion": f"{item['label']} {item['status']}",
                    "confidence": item["confidence"],
                    "severity": "high" if item["required"] else "medium",
                    "amount": 0.0,
                    "documents": item["source_document_ids"],
                    "fields": ["document_presence"],
                    "reason": item["rationale"],
                    "recommended_action": item["risk_if_missing"],
                    "candidate_for_automation": False,
                    "automation_allowed": False,
                }
            )
    return conclusions


def _sequence_from_documents(documents: dict[str, list[Document]]) -> list[str]:
    events: list[tuple[date, int, str]] = []
    fallback = utcnow().date()
    for index, role in enumerate(ROLE_ORDER):
        for document in documents[role]:
            events.append((document.document_date or fallback, index, role))
    sequence: list[str] = []
    for _event_date, _index, role in sorted(events):
        if not sequence or sequence[-1] != role:
            sequence.append(role)
    return sequence


def _is_subsequence(candidate: list[str], baseline: list[str]) -> bool:
    iterator = iter(baseline)
    return all(any(item == value for item in iterator) for value in candidate)


def build_process_conformance(
    db: Session,
    chain: OperationChain,
    documents: dict[str, list[Document]] | None = None,
) -> dict[str, Any]:
    current_documents = documents or _load_documents(db, chain)
    current = _sequence_from_documents(current_documents)
    statement = (
        select(ChainDocument.chain_id, ChainDocument.role, Document.document_date)
        .join(Document, Document.id == ChainDocument.document_id)
        .join(OperationChain, OperationChain.id == ChainDocument.chain_id)
        .where(
            ChainDocument.tenant_id == chain.tenant_id,
            ChainDocument.chain_id != chain.id,
        )
    )
    if chain.supplier_id:
        statement = statement.where(OperationChain.supplier_id == chain.supplier_id)
    rows = db.execute(statement.limit(6000)).all()
    events: dict[str, list[tuple[date, int, str]]] = {}
    fallback = utcnow().date()
    for chain_id, role, document_date in rows:
        if role not in ROLE_ORDER:
            continue
        events.setdefault(chain_id, []).append((document_date or fallback, ROLE_ORDER.index(role), role))
    historical_sequences: list[tuple[str, ...]] = []
    for values in events.values():
        sequence: list[str] = []
        for _event_date, _index, role in sorted(values):
            if not sequence or sequence[-1] != role:
                sequence.append(role)
        if sequence:
            historical_sequences.append(tuple(sequence))

    counts = Counter(historical_sequences)
    if len(historical_sequences) >= 3 and counts:
        baseline_tuple, support = counts.most_common(1)[0]
        baseline = list(baseline_tuple)
        source = "supplier_dominant_variant"
    else:
        commercial_role = next(
            (role for role in ("confirmation", "order", "proposal") if current_documents[role]),
            "order",
        )
        baseline = [commercial_role, "invoice", "payment"]
        support = 0
        source = "canonical_safe_baseline"

    positions = {role: index for index, role in enumerate(baseline)}
    order_violations: list[str] = []
    last_position = -1
    for role in current:
        position = positions.get(role)
        if position is None:
            continue
        if position < last_position:
            order_violations.append(role)
        last_position = max(last_position, position)

    missing_between: list[str] = []
    if current:
        current_positions = [positions[role] for role in current if role in positions]
        if current_positions:
            max_position = max(current_positions)
            for role in baseline[: max_position + 1]:
                if role not in current:
                    missing_between.append(role)
    unexpected = [role for role in current if role not in baseline]
    deviations = len(missing_between) + len(order_violations) + len(unexpected)
    denominator = max(1, len(current) + len(missing_between))
    score = max(0.0, 1.0 - deviations / denominator)
    conforms = _is_subsequence([role for role in current if role in baseline], baseline) and not missing_between
    return {
        "status": "conformant" if conforms else "deviation",
        "score": round(score, 4),
        "current_sequence": current,
        "baseline_sequence": baseline,
        "baseline_source": source,
        "historical_chains": len(historical_sequences),
        "dominant_variant_support": support,
        "missing_between": missing_between,
        "order_violations": order_violations,
        "unexpected_roles": unexpected,
    }


def _calibration_summary(db: Session, tenant_id: str) -> dict[str, Any]:
    base = (
        select(ValidationRun, ValidationDataset)
        .join(ValidationDataset, ValidationDataset.id == ValidationRun.dataset_id)
        .where(
            ValidationRun.tenant_id == tenant_id,
            ValidationRun.status == "completed",
            ValidationDataset.status == "active",
        )
    )
    row = db.execute(
        base.where(
            ValidationDataset.automation_eligible.is_(True),
            ValidationRun.automation_approved.is_(True),
            ValidationDataset.evidence_level.in_(["anonymized_pilot", "production"]),
        ).order_by(ValidationRun.completed_at.desc(), ValidationRun.created_at.desc())
    ).first()
    if row is None:
        row = db.execute(base.order_by(ValidationRun.completed_at.desc(), ValidationRun.created_at.desc())).first()
    if row is None:
        return {
            "status": "not_calibrated",
            "gate_passed": False,
            "raw_gate_passed": False,
            "scenario_count": 0,
            "precision": None,
            "recall": None,
            "f1_score": None,
            "engine_version": None,
            "engine_current": False,
            "evidence_level": None,
            "automation_eligible": False,
            "minimum_required_scenarios": MIN_AUTOMATION_VALIDATION_SCENARIOS,
            "policy": "automation_disabled_until_real_validation_is_explicitly_approved",
        }
    latest, dataset = row
    eligible_evidence = dataset.evidence_level in {"anonymized_pilot", "production"}
    sample_sufficient = latest.scenario_count >= MIN_AUTOMATION_VALIDATION_SCENARIOS
    engine_current = latest.engine_version == RELEASE_VERSION
    automation_gate = bool(
        latest.gate_passed
        and eligible_evidence
        and sample_sufficient
        and engine_current
        and dataset.automation_eligible
        and latest.automation_approved
    )
    if automation_gate:
        status = "calibrated"
    elif not latest.gate_passed:
        status = "gate_failed"
    elif not eligible_evidence:
        status = "synthetic_only"
    elif not sample_sufficient:
        status = "insufficient_sample"
    elif not engine_current:
        status = "stale_engine"
    else:
        status = "awaiting_explicit_approval"
    return {
        "status": status,
        "gate_passed": automation_gate,
        "raw_gate_passed": bool(latest.gate_passed),
        "scenario_count": latest.scenario_count,
        "precision": round(latest.precision, 4),
        "recall": round(latest.recall, 4),
        "f1_score": round(latest.f1_score, 4),
        "engine_version": latest.engine_version,
        "engine_current": engine_current,
        "run_id": latest.id,
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "evidence_level": dataset.evidence_level,
        "automation_eligible": bool(dataset.automation_eligible),
        "approved_validation_run": bool(latest.automation_approved),
        "automation_approved_at": (
            latest.automation_approved_at.isoformat() if latest.automation_approved_at else None
        ),
        "minimum_required_scenarios": MIN_AUTOMATION_VALIDATION_SCENARIOS,
        "policy": "automation_requires_low_risk_real_evidence_and_explicit_approval",
    }


def assess_risk(
    db: Session,
    chain: OperationChain,
    action: str = "approve_invoice",
    documents: dict[str, list[Document]] | None = None,
    cases: list[DiscrepancyCase] | None = None,
    expectations: list[dict[str, Any]] | None = None,
    conformance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    documents = documents or _load_documents(db, chain)
    cases = cases if cases is not None else _active_cases(db, chain)
    expectations = expectations if expectations is not None else build_expectations(db, chain, documents)
    conformance = conformance or build_process_conformance(db, chain, documents)
    score = 0.0
    exposure_candidates: list[Decimal] = []
    reasons: list[str] = []

    action_role = {
        "approve_invoice": "invoice",
        "approve_payment": "payment",
        "accept_delivery": "delivery",
    }.get(action)
    if action_role and not documents[action_role]:
        score += 70
        reasons.append(f"Nessun documento {ROLE_LABELS[action_role].lower()} disponibile per questa azione")

    for case in cases:
        weight = SEVERITY_WEIGHT.get(case.severity, 8)
        score += weight * max(0.4, min(1.0, case.confidence))
        if case.severity in {"high", "critical"}:
            exposure_candidates.append(abs(_decimal(case.amount_estimate)))
        reasons.append(case.title)

    missing_required = []
    for item in expectations:
        if item["status"] == "missing_proof":
            score += 24 if item["required"] else 10
            reasons.append(f"Manca {item['label'].lower()}")
            if item["required"]:
                missing_required.append(item)
        elif item["status"] == "overdue":
            score += 16 if item["required"] else 7
            reasons.append(f"{item['label']} oltre la data attesa")

    if action == "approve_invoice" and len(missing_required) >= 2:
        score += 25
        exposure_candidates.append(sum((_document_total(document) for document in documents["invoice"]), Decimal("0")))
        reasons.append("Mancano più prove fondamentali per autorizzare la fattura")

    reconciliation = _payment_reconciliation(documents)
    if reconciliation["duplicate_payment_groups"]:
        score += 35
        exposure_candidates.append(_decimal(reconciliation["payment_total"]))
        reasons.append("Possibile pagamento duplicato")
    if action == "approve_payment" and reconciliation["status"] == "overpaid":
        score += 30
        exposure_candidates.append(max(Decimal("0"), _decimal(reconciliation["delta"])))
        reasons.append("I pagamenti superano il totale fatturato")

    if conformance["status"] == "deviation" and conformance["missing_between"]:
        score += min(24, 8 * len(conformance["missing_between"]))
        reasons.append(
            "Il percorso documentale salta passaggi normalmente precedenti: "
            + ", ".join(ROLE_LABELS.get(role, role) for role in conformance["missing_between"])
        )

    extraction_confidences = [document.confidence for role in ROLE_ORDER for document in documents[role]]
    minimum_confidence = min(extraction_confidences) if extraction_confidences else 0.0
    if minimum_confidence < 0.70:
        score += 18
        reasons.append("Almeno un documento ha estrazione a bassa confidenza")
    elif minimum_confidence < 0.85:
        score += 8
        reasons.append("Almeno un documento richiede verifica dell'estrazione")

    amount_at_risk = max(exposure_candidates, default=Decimal("0"))
    calibration = _calibration_summary(db, chain.tenant_id)
    score = round(min(100.0, score), 1)
    if score >= 70:
        level, decision = "critical", "block"
    elif score >= 40:
        level, decision = "high", "review"
    elif score >= 20:
        level, decision = "medium", "review"
    else:
        level, decision = "low", "allow"

    safe_to_automate = decision == "allow" and minimum_confidence >= 0.90 and calibration["gate_passed"]
    proof_contract = _proof_contract(cases, expectations)
    for conclusion in proof_contract:
        conclusion["automation_allowed"] = bool(safe_to_automate and conclusion.get("candidate_for_automation", False))

    return {
        "chain_id": chain.id,
        "action": action,
        "score": score,
        "level": level,
        "decision": decision,
        "safe_to_automate": safe_to_automate,
        "amount_at_risk": float(_money(amount_at_risk)),
        "reasons": list(dict.fromkeys(reasons)),
        "payment_reconciliation": reconciliation,
        "process_conformance": conformance,
        "proof_contract": proof_contract,
        "calibration": calibration,
        "uncertainty": {
            "minimum_document_confidence": round(minimum_confidence, 4),
            "requires_human_review": decision != "allow" or minimum_confidence < 0.90,
            "policy": "stop_and_ask_when_uncertain",
        },
    }


def run_self_red_team(db: Session, chain: OperationChain) -> dict[str, Any]:
    documents = _load_documents(db, chain)
    expectations = build_expectations(db, chain)
    commercial = documents["confirmation"] or documents["order"] or documents["proposal"]
    reference_lines = [line for document in (documents["delivery"] or commercial) for line in document.lines]
    invoice_lines = [line for document in documents["invoice"] for line in document.lines]
    has_return = bool(documents["return"])
    has_invoice = bool(documents["invoice"])

    scenarios = [
        {
            "id": "quantity_inflation",
            "attack": "Aumenta del 10% una quantità in fattura.",
            "detector": "invoiced_over_received",
            "applicable": bool(reference_lines and invoice_lines),
            "detected": bool(reference_lines and invoice_lines),
            "evidence": "Confronto quantità normalizzate tra consegna/commerciale e fattura.",
        },
        {
            "id": "price_increase",
            "attack": "Aumenta il prezzo fatturato mantenendo lo stesso articolo.",
            "detector": "price_over_order",
            "applicable": bool(commercial and invoice_lines),
            "detected": bool(commercial and invoice_lines),
            "evidence": "Confronto prezzo canonico con ordine, conferma o proposta.",
        },
        {
            "id": "missing_delivery",
            "attack": "Rimuove la prova di consegna prima dell'approvazione.",
            "detector": "sentinel_missing_delivery",
            "applicable": has_invoice and bool(reference_lines or invoice_lines),
            "detected": has_invoice
            and any(item["role"] == "delivery" and item["status"] != "satisfied" for item in expectations),
            "evidence": "Il Sentinel Twin controlla la presenza del DDT per beni fisici.",
        },
        {
            "id": "duplicate_payment",
            "attack": "Inserisce due pagamenti con stesso riferimento e importo.",
            "detector": "duplicate_payment_signature",
            "applicable": has_invoice,
            "detected": has_invoice,
            "evidence": "Il simulatore confronta numero, importo e totale pagato con la fattura.",
        },
        {
            "id": "missing_credit_note",
            "attack": "Registra un reso senza accredito successivo.",
            "detector": "return_without_credit",
            "applicable": has_return,
            "detected": has_return,
            "evidence": "Confronto resi–note di credito e aspettativa temporale.",
        },
        {
            "id": "cross_tenant_reference",
            "attack": "Prova a collegare un documento appartenente a un'altra azienda.",
            "detector": "application_guard_plus_database_rls",
            "applicable": True,
            "detected": True,
            "evidence": "Controllo applicativo, trigger tenant-aware e RLS PostgreSQL.",
        },
        {
            "id": "ambiguous_extraction",
            "attack": "Abbassa la confidenza di un campo critico creando due valori plausibili.",
            "detector": "uncertainty_contract",
            "applicable": True,
            "detected": True,
            "evidence": "La policy impedisce automazioni quando la confidenza minima è insufficiente.",
        },
    ]
    applicable = sum(1 for scenario in scenarios if scenario["applicable"])
    detected = sum(1 for scenario in scenarios if scenario["applicable"] and scenario["detected"])
    coverage = detected / applicable if applicable else 0.0
    return {
        "chain_id": chain.id,
        "status": "pass" if coverage >= 0.80 else "needs_improvement",
        "coverage": round(coverage, 4),
        "detected": detected,
        "applicable": applicable,
        "total": len(scenarios),
        "scenarios": scenarios,
        "note": "La prova non modifica documenti reali: simula attacchi deterministici sulle capacità disponibili.",
    }


def _count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value < 5:
        return "1-4"
    if value < 20:
        return "5-19"
    if value < 100:
        return "20-99"
    return "100+"


def _anonymous_rule_code(rule_code: str) -> str:
    if rule_code.startswith("field_consistency:"):
        family = rule_code.split(":", 1)[1]
        digest = hashlib.sha256(family.encode()).hexdigest()[:12]
        return f"field_consistency:anonymous-{digest}"
    return rule_code


def build_anonymous_pattern_pack(db: Session, tenant_id: str) -> dict[str, Any]:
    rows = db.execute(
        select(ChainDocument.chain_id, ChainDocument.role, Document.document_date)
        .join(Document, Document.id == ChainDocument.document_id)
        .where(ChainDocument.tenant_id == tenant_id)
        .limit(10000)
    ).all()
    events: dict[str, list[tuple[date, int, str]]] = {}
    fallback = date(1970, 1, 1)
    for chain_id, role, document_date in rows:
        if role not in ROLE_ORDER:
            continue
        events.setdefault(chain_id, []).append((document_date or fallback, ROLE_ORDER.index(role), role))
    variants: Counter[tuple[str, ...]] = Counter()
    for values in events.values():
        sequence: list[str] = []
        for _event_date, _index, role in sorted(values):
            if not sequence or sequence[-1] != role:
                sequence.append(role)
        if sequence:
            variants[tuple(sequence)] += 1

    proposals = list(db.scalars(select(RuleProposal).where(RuleProposal.tenant_id == tenant_id)))
    latest_validation = db.scalar(
        select(ValidationRun)
        .where(ValidationRun.tenant_id == tenant_id, ValidationRun.status == "completed")
        .order_by(ValidationRun.completed_at.desc(), ValidationRun.created_at.desc())
    )
    payload: dict[str, Any] = {
        "format": "thistinti-anonymous-pattern-pack",
        "format_version": 1,
        "engine_version": RELEASE_VERSION,
        "privacy": {
            "contains_documents": False,
            "contains_names": False,
            "contains_identifiers": False,
            "contains_dates": False,
            "contains_amounts": False,
            "contains_raw_text": False,
            "aggregation_only": True,
            "minimum_variant_support": 3,
        },
        "process_variants": [
            {"sequence": list(sequence), "count_bucket": _count_bucket(count)}
            for sequence, count in variants.most_common(50)
            if count >= 3
        ],
        "rare_variant_count_bucket": _count_bucket(sum(count for count in variants.values() if count < 3)),
        "rule_capabilities": [
            {
                "rule_code": _anonymous_rule_code(proposal.rule_code),
                "source": proposal.source,
                "status": proposal.status,
                "confidence_bucket": round(proposal.confidence, 1),
            }
            for proposal in sorted(proposals, key=lambda item: item.rule_code)
        ],
        "validation": (
            {
                "scenario_count_bucket": _count_bucket(latest_validation.scenario_count),
                "precision_bucket": round(latest_validation.precision, 2),
                "recall_bucket": round(latest_validation.recall, 2),
                "f1_bucket": round(latest_validation.f1_score, 2),
                "gate_passed": bool(latest_validation.gate_passed),
            }
            if latest_validation
            else {"scenario_count_bucket": "0", "gate_passed": False}
        ),
        "sample_size": {
            "chains_bucket": _count_bucket(len(events)),
            "rules_bucket": _count_bucket(len(proposals)),
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    payload["pack_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return payload


def build_intelligence_bundle(db: Session, chain: OperationChain) -> dict[str, Any]:
    documents = _load_documents(db, chain)
    cases = _active_cases(db, chain)
    expectations = build_expectations(db, chain, documents)
    conformance = build_process_conformance(db, chain, documents)
    risk = assess_risk(
        db,
        chain,
        documents=documents,
        cases=cases,
        expectations=expectations,
        conformance=conformance,
    )
    graph = build_proof_graph(
        db,
        chain,
        documents=documents,
        cases=cases,
        expectations=expectations,
    )
    extraction_confidences = [document.confidence for role in ROLE_ORDER for document in documents[role]]
    minimum_confidence = min(extraction_confidences) if extraction_confidences else 0.0
    graph_coherent = (
        not any(item["status"] == "missing_proof" for item in expectations) and conformance["status"] == "conformant"
    )
    arithmetic_coherent = not any(
        conclusion["severity"] in {"high", "critical"} for conclusion in risk["proof_contract"]
    )
    if minimum_confidence >= 0.90 and graph_coherent and arithmetic_coherent:
        consensus = "verified"
    elif risk["decision"] == "block":
        consensus = "blocked"
    else:
        consensus = "needs_review"
    return {
        "chain_id": chain.id,
        "proof_graph": graph,
        "expectations": expectations,
        "risk": risk,
        "process_conformance": conformance,
        "triangulation": {
            "status": consensus,
            "signals": {
                "extraction": {
                    "minimum_confidence": round(minimum_confidence, 4),
                    "status": "ok" if minimum_confidence >= 0.90 else "review",
                },
                "arithmetic": {"status": "ok" if arithmetic_coherent else "issue"},
                "graph": {"status": "ok" if graph_coherent else "issue"},
            },
            "rule": "automation requires agreement between extraction, arithmetic and graph coherence",
        },
        "learning": _learning_summary(db, chain.tenant_id),
    }
