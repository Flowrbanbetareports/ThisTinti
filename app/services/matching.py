from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ChainDocument, Document, OperationChain
from .normalizer import item_similarity, normalize_code

PRIMARY_FIELD_BY_TYPE = {
    "proposal": "proposal_document_id",
    "order": "order_document_id",
    "confirmation": "confirmation_document_id",
    "delivery": "delivery_document_id",
    "invoice": "invoice_document_id",
    "payment": "payment_document_id",
    "return": "return_document_id",
    "credit_note": "credit_note_document_id",
}


def _references(document: Document) -> dict:
    try:
        return json.loads(document.references_json or "{}")
    except json.JSONDecodeError:
        return {}


def _candidate_reference(document: Document) -> str | None:
    refs = _references(document)
    for key in ("order_numbers", "invoice_numbers", "delivery_numbers"):
        values = refs.get(key) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            normalized = normalize_code(str(value))
            if normalized:
                return normalized
    if document.document_type in {"proposal", "order"} and document.number:
        return normalize_code(document.number)
    return None


def _line_overlap(a: Document, b: Document) -> float:
    """Return conservative one-to-one overlap, exact first and fuzzy only at high confidence."""
    a_keys = Counter(line.canonical_key for line in a.lines if line.canonical_key)
    b_keys = Counter(line.canonical_key for line in b.lines if line.canonical_key)
    if not a_keys or not b_keys:
        return 0.0

    exact = sum(min(a_keys[k], b_keys[k]) for k in a_keys.keys() & b_keys.keys())
    remaining_a: list[str] = []
    remaining_b: list[str] = []
    for key, count in a_keys.items():
        remaining_a.extend([key] * max(0, count - min(count, b_keys.get(key, 0))))
    for key, count in b_keys.items():
        remaining_b.extend([key] * max(0, count - min(count, a_keys.get(key, 0))))

    fuzzy = 0
    while remaining_a and remaining_b:
        best: tuple[float, int, int] | None = None
        for a_index, a_key in enumerate(remaining_a):
            for b_index, b_key in enumerate(remaining_b):
                score = item_similarity(a_key, b_key)
                if best is None or score > best[0]:
                    best = (score, a_index, b_index)
        if best is None or best[0] < 0.90:
            break
        fuzzy += 1
        remaining_a.pop(best[1])
        remaining_b.pop(best[2])

    return (exact + fuzzy) / max(sum(a_keys.values()), sum(b_keys.values()))


def _anchor_documents(db: Session, chain: OperationChain) -> list[Document]:
    ids = list(
        db.scalars(
            select(ChainDocument.document_id).where(
                ChainDocument.tenant_id == chain.tenant_id,
                ChainDocument.chain_id == chain.id,
                ChainDocument.role.in_(["proposal", "order", "confirmation", "delivery", "invoice", "payment"]),
            )
        )
    )
    return list(db.scalars(select(Document).where(Document.id.in_(ids)))) if ids else []


def attach_document_to_chain(db: Session, document: Document) -> OperationChain:
    reference = _candidate_reference(document)
    chain = None
    match_reason = "new_chain"
    match_confidence = 1.0 if document.document_type in {"proposal", "order"} else 0.45

    if reference:
        reference_candidates = list(
            db.scalars(
                select(Document)
                .where(
                    Document.tenant_id == document.tenant_id,
                    Document.supplier_id == document.supplier_id,
                    Document.number.is_not(None),
                )
                .order_by(Document.created_at.desc())
                .limit(500)
            )
        )
        referenced_document = next(
            (candidate for candidate in reference_candidates if normalize_code(candidate.number or "") == reference),
            None,
        )
        if referenced_document:
            chain = db.scalar(
                select(OperationChain)
                .join(ChainDocument, ChainDocument.chain_id == OperationChain.id)
                .where(
                    OperationChain.tenant_id == document.tenant_id,
                    ChainDocument.document_id == referenced_document.id,
                )
                .order_by(OperationChain.updated_at.desc())
            )
        if chain is None:
            chain = db.scalar(
                select(OperationChain)
                .where(
                    OperationChain.tenant_id == document.tenant_id,
                    OperationChain.supplier_id == document.supplier_id,
                    OperationChain.reference_key == reference,
                )
                .order_by(OperationChain.updated_at.desc())
            )
        if chain:
            match_reason = "explicit_reference"
            match_confidence = 1.0

    if chain is None and document.document_type not in {"proposal", "order"} and document.supplier_id:
        candidates = list(
            db.scalars(
                select(OperationChain)
                .where(
                    OperationChain.tenant_id == document.tenant_id,
                    OperationChain.supplier_id == document.supplier_id,
                    OperationChain.status.in_(["open", "review", "clear"]),
                )
                .order_by(OperationChain.updated_at.desc())
                .limit(30)
            )
        )
        scored: list[tuple[float, OperationChain]] = []
        for candidate in candidates:
            anchors = _anchor_documents(db, candidate)
            if not anchors:
                continue
            score = max(_line_overlap(document, anchor) for anchor in anchors)
            dated = [a for a in anchors if a.document_date and document.document_date]
            if dated:
                days = min(abs((document.document_date - a.document_date).days) for a in dated)
                if days <= 60:
                    score += 0.08
                elif days > 180:
                    score -= 0.2
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored and scored[0][0] >= 0.68 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.12):
            match_confidence, chain = min(1.0, scored[0][0]), scored[0][1]
            match_reason = "line_overlap"

    if chain is None:
        chain = OperationChain(
            tenant_id=document.tenant_id,
            supplier_id=document.supplier_id,
            reference_key=reference
            or (normalize_code(document.number) if document.document_type in {"proposal", "order"} else None),
            confidence=match_confidence,
        )
        db.add(chain)
        db.flush()

    existing_link = db.scalar(
        select(ChainDocument).where(
            ChainDocument.tenant_id == document.tenant_id,
            ChainDocument.chain_id == chain.id,
            ChainDocument.document_id == document.id,
        )
    )
    if not existing_link:
        sequence = (
            db.scalar(
                select(func.count(ChainDocument.id)).where(
                    ChainDocument.chain_id == chain.id,
                    ChainDocument.role == document.document_type,
                )
            )
            or 0
        )
        db.add(
            ChainDocument(
                tenant_id=document.tenant_id,
                chain_id=chain.id,
                document_id=document.id,
                role=document.document_type,
                sequence_no=int(sequence) + 1,
                match_confidence=match_confidence,
                match_reason=match_reason,
            )
        )

    primary_field = PRIMARY_FIELD_BY_TYPE[document.document_type]
    if not getattr(chain, primary_field):
        setattr(chain, primary_field, document.id)
    if document.document_type in {"proposal", "order"} and not chain.reference_key and document.number:
        chain.reference_key = normalize_code(document.number)
    chain.confidence = max(chain.confidence, match_confidence)
    db.flush()
    return chain
