from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import ChainDocument, Document, DocumentLine, OperationChain
from .line_matching import group_chain_lines
from .units import canonical_unit_price, quantity_profile

ROLES = ("proposal", "order", "confirmation", "delivery", "invoice", "payment", "return", "credit_note")


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _display(value: Decimal, places: str) -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def chain_documents_by_role(db: Session, chain: OperationChain) -> dict[str, list[Document]]:
    links = list(
        db.scalars(
            select(ChainDocument)
            .where(ChainDocument.tenant_id == chain.tenant_id, ChainDocument.chain_id == chain.id)
            .order_by(ChainDocument.role, ChainDocument.sequence_no)
        )
    )
    document_ids = [link.document_id for link in links]
    docs = (
        list(
            db.scalars(
                select(Document)
                .options(selectinload(Document.lines))
                .where(Document.tenant_id == chain.tenant_id, Document.id.in_(document_ids))
            )
        )
        if document_ids
        else []
    )
    by_id = {document.id: document for document in docs}
    grouped: dict[str, list[Document]] = {role: [] for role in ROLES}
    for link in links:
        document = by_id.get(link.document_id)
        if document:
            grouped[link.role].append(document)
    return grouped


def _aggregate(lines: list[DocumentLine]) -> dict | None:
    if not lines:
        return None
    profile = quantity_profile(lines)
    raw_quantity = sum((_decimal(line.quantity) for line in lines), Decimal("0"))
    weights = [
        abs(quantity_profile([line]).quantity) if quantity_profile([line]).compatible else abs(_decimal(line.quantity))
        for line in lines
    ]
    absolute_qty = sum(weights, Decimal("0"))
    normalized_prices = [
        canonical_unit_price(line.unit_price, line.price_base_quantity, line.unit_of_measure) for line in lines
    ]
    unit_price = (
        sum((weight * price for weight, price in zip(weights, normalized_prices, strict=True)), Decimal("0"))
        / absolute_qty
        if absolute_qty
        else Decimal("0")
    )
    discount = (
        sum((weight * _decimal(line.discount_rate) for weight, line in zip(weights, lines, strict=True)), Decimal("0"))
        / absolute_qty
        if absolute_qty
        else Decimal("0")
    )
    units = list(profile.source_units)
    return {
        "quantity": _display(profile.quantity if profile.compatible else raw_quantity, "0.0001"),
        "unit_price": _display(unit_price, "0.000001"),
        "discount_rate": _display(discount, "0.0001"),
        "line_total": _display(sum((_decimal(line.line_total) for line in lines), Decimal("0")), "0.01"),
        "unit_of_measure": profile.unit if profile.compatible else (units[0] if len(units) == 1 else (units or None)),
        "source_units": units,
        "dimension": profile.dimension,
        "comparable": profile.compatible,
        "line_ids": [line.id for line in lines],
        "document_ids": sorted({line.document_id for line in lines}),
    }


def build_chain_comparison(db: Session, chain: OperationChain) -> dict:
    documents = chain_documents_by_role(db, chain)
    grouped = group_chain_lines(db, chain, documents)
    keys = sorted({key for role_groups in grouped.values() for key in role_groups})
    rows: list[dict] = []
    for key in keys:
        all_lines = [line for role in ROLES for line in grouped.get(role, {}).get(key, [])]
        exemplar = next((line for line in all_lines if line.sku), all_lines[0])
        values = {role: _aggregate(grouped.get(role, {}).get(key, [])) for role in ROLES}
        commercial = values["confirmation"] or values["order"] or values["proposal"]
        commercial_source = "confirmation" if values["confirmation"] else "order" if values["order"] else "proposal"
        delivery = values["delivery"]
        invoice = values["invoice"]
        status = "ok"
        reasons: list[str] = []
        reference = delivery or commercial
        quantity_compatible = bool(
            invoice
            and reference
            and invoice["comparable"]
            and reference["comparable"]
            and (
                (invoice["dimension"] is None and reference["dimension"] is None)
                or invoice["dimension"] == reference["dimension"]
            )
        )
        commercial_compatible = bool(
            invoice
            and commercial
            and invoice["comparable"]
            and commercial["comparable"]
            and (
                (invoice["dimension"] is None and commercial["dimension"] is None)
                or invoice["dimension"] == commercial["dimension"]
            )
        )
        if invoice and reference and not quantity_compatible:
            status = "issue"
            reasons.append("unità di misura incompatibili")
        elif quantity_compatible:
            reference_qty = reference["quantity"]
            if invoice["quantity"] > reference_qty + 1e-6:
                status = "issue"
                reasons.append("quantità fatturata superiore")
        if invoice and commercial:
            if not commercial_compatible:
                status = "issue"
                if "unità di misura incompatibili" not in reasons:
                    reasons.append("unità di misura incompatibili")
            elif invoice["unit_price"] > commercial["unit_price"] + 0.005:
                status = "issue"
                reasons.append("prezzo superiore")
            if commercial["discount_rate"] > invoice["discount_rate"] + 0.01:
                status = "issue"
                reasons.append("sconto inferiore")
        if invoice and not commercial and not delivery:
            status = "unmatched"
            reasons.append("riga fattura non collegata")
        rows.append(
            {
                "key": key,
                "sku": exemplar.sku,
                "description": exemplar.description,
                "color": exemplar.color,
                "size": exemplar.size,
                "lot": exemplar.lot,
                "unit_of_measure": exemplar.unit_of_measure,
                "commercial_source": commercial_source,
                "status": status,
                "reasons": reasons,
                "values": values,
            }
        )
    return {
        "documents": {
            role: [
                {
                    "id": document.id,
                    "number": document.number,
                    "source_filename": document.source_filename,
                    "document_date": document.document_date.isoformat() if document.document_date else None,
                    "confidence": document.confidence,
                    "parse_status": document.parse_status,
                }
                for document in role_documents
            ]
            for role, role_documents in documents.items()
        },
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "issue_count": sum(row["status"] == "issue" for row in rows),
            "unmatched_count": sum(row["status"] == "unmatched" for row in rows),
        },
    }
