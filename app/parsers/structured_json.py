from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from .base import (
    ParsedDocument,
    ParsedLine,
    ParseError,
    effective_discount_rate,
    parse_date,
    safe_decimal,
)


def _rates(value) -> list[Decimal]:
    if value in (None, ""):
        return []
    values = value if isinstance(value, list) else [value]
    return [safe_decimal(item) for item in values]


def parse_json(path: Path, overrides: dict) -> ParsedDocument:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ParseError(f"JSON non valido: {exc}") from exc
    doc = ParsedDocument(
        document_type=overrides.get("document_type") or data.get("document_type"),
        number=overrides.get("number") or data.get("number"),
        document_date=parse_date(overrides.get("document_date") or data.get("document_date")),
        currency=str(data.get("currency", "EUR")).upper(),
        supplier_name=overrides.get("supplier_name") or data.get("supplier_name"),
        supplier_vat=data.get("supplier_vat"),
        references=data.get("references", {}),
        metadata=data.get("metadata", {}),
        confidence=0.99,
    )
    if not doc.document_type:
        raise ParseError("document_type mancante nel JSON e negli override")
    for idx, item in enumerate(data.get("lines", []), start=1):
        qty = safe_decimal(item.get("quantity"))
        price = safe_decimal(item.get("unit_price"))
        base_qty = safe_decimal(item.get("price_base_quantity"), 1)
        if base_qty == 0:
            base_qty = Decimal("1")
        discounts = _rates(item.get("discounts"))
        charges = _rates(item.get("charges"))
        if discounts or charges:
            discount = effective_discount_rate(discounts, charges)
        else:
            discount = safe_decimal(item.get("discount_rate"))
        expected = (qty * price / base_qty) * (Decimal("1") - discount / Decimal("100"))
        line_total = safe_decimal(item.get("line_total"), expected)
        raw = dict(item)
        if discounts:
            raw["discount_components"] = [str(value) for value in discounts]
        if charges:
            raw["charge_components"] = [str(value) for value in charges]
        doc.lines.append(
            ParsedLine(
                line_no=int(item.get("line_no", idx)),
                sku=item.get("sku"),
                description=item.get("description"),
                color=item.get("color"),
                size=item.get("size"),
                lot=item.get("lot"),
                unit_of_measure=item.get("unit_of_measure") or item.get("uom"),
                quantity=qty,
                unit_price=price,
                price_base_quantity=base_qty,
                discount_rate=discount,
                tax_rate=safe_decimal(item.get("tax_rate")),
                line_total=line_total,
                confidence=float(item.get("confidence", 0.99)),
                raw=raw,
            )
        )
    return doc
