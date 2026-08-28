from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .base import (
    ParsedDocument,
    ParsedLine,
    ParseError,
    effective_discount_rate,
    parse_date,
    parse_decimal_field,
    parse_integer_field,
)

DOCUMENT_TYPES = {
    "proposal",
    "order",
    "confirmation",
    "delivery",
    "invoice",
    "payment",
    "return",
    "credit_note",
}
PRICE_OPTIONAL_TYPES = {"delivery", "return"}
LEGACY_REFERENCE_KEYS = {
    "confirmation": "order_numbers",
    "delivery": "order_numbers",
    "invoice": "order_numbers",
    "payment": "invoice_numbers",
    "return": "invoice_numbers",
    "credit_note": "invoice_numbers",
}


def _structure_error(reason: str, *, line: int | None = None, field: str | None = None, value: Any = None):
    raise ParseError(
        f"Struttura JSON non valida: {reason}",
        code="invalid_document_structure",
        line=line,
        field=field,
        value=value,
        reason=reason,
    )


def _supplier(data: dict[str, Any]) -> tuple[str | None, str | None]:
    nested = data.get("supplier")
    if nested is not None and not isinstance(nested, dict):
        _structure_error("supplier deve essere un oggetto", field="supplier", value=nested)
    nested = nested or {}
    name = data.get("supplier_name")
    vat_id = data.get("supplier_vat")
    if name is None:
        name = nested.get("name") or nested.get("legal_name")
    if vat_id is None:
        vat_id = nested.get("vat_id") or nested.get("vat")
    return (
        str(name).strip() or None if name is not None else None,
        str(vat_id).strip() or None if vat_id is not None else None,
    )


def _references(value: Any, document_type: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, list):
        if not all(isinstance(item, (str, int)) and str(item).strip() for item in value):
            _structure_error(
                "references in forma elenco può contenere soltanto identificativi",
                field="references",
                value=value,
            )
        key = LEGACY_REFERENCE_KEYS.get(document_type, "document_numbers")
        return {key: [str(item).strip() for item in value]}
    if not isinstance(value, dict):
        _structure_error(
            "references deve essere un oggetto o un elenco di identificativi", field="references", value=value
        )

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            _structure_error("le chiavi di references devono essere stringhe non vuote", field="references", value=key)
        if key.endswith("_numbers"):
            numbers = item if isinstance(item, list) else [item]
            if not all(isinstance(number, (str, int)) and str(number).strip() for number in numbers):
                _structure_error(
                    f"{key} deve contenere soltanto identificativi",
                    field=f"references.{key}",
                    value=item,
                )
            normalized[key] = [str(number).strip() for number in numbers]
        else:
            normalized[key] = item
    return normalized


def _rates(value: Any, *, field: str, line: int, provenance: dict[str, str]) -> list[Decimal]:
    if value in (None, ""):
        return []
    values = value if isinstance(value, list) else [value]
    rates = [
        parse_decimal_field(
            item,
            field=f"{field}[{index}]",
            line=line,
            required=True,
            max_decimal_places=6,
            minimum=0,
            maximum=100,
        )
        for index, item in enumerate(values)
    ]
    if rates:
        provenance["discount_rate"] = "derived"
    return rates


def _parse_confidence(value: Any, *, line: int) -> float:
    return float(
        parse_decimal_field(
            value,
            field="confidence",
            line=line,
            default=Decimal("0.99"),
            max_decimal_places=6,
            minimum=0,
            maximum=1,
        )
    )


def parse_json(path: Path, overrides: dict) -> ParsedDocument:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ParseError(
            f"JSON non valido: {exc}",
            code="invalid_document_structure",
            reason="Il contenuto non è un documento JSON valido",
        ) from exc
    if not isinstance(data, dict):
        _structure_error("il valore principale deve essere un oggetto")

    document_type = overrides.get("document_type") or data.get("document_type")
    if not document_type:
        _structure_error("document_type è obbligatorio", field="document_type")
    if document_type not in DOCUMENT_TYPES:
        _structure_error(
            f"document_type non supportato: {document_type}",
            field="document_type",
            value=document_type,
        )

    lines = data.get("lines", [])
    if not isinstance(lines, list):
        _structure_error("lines deve essere un elenco", field="lines", value=lines)
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        _structure_error("metadata deve essere un oggetto", field="metadata", value=metadata)
    supplier_name, supplier_vat = _supplier(data)
    currency = data.get("currency", "EUR")
    if not isinstance(currency, str) or not currency.strip() or len(currency.strip()) > 8:
        _structure_error(
            "currency deve essere una stringa non vuota di massimo 8 caratteri", field="currency", value=currency
        )

    doc = ParsedDocument(
        document_type=document_type,
        number=overrides.get("number") or data.get("number"),
        document_date=parse_date(overrides.get("document_date") or data.get("document_date")),
        currency=currency.strip().upper(),
        supplier_name=overrides.get("supplier_name") or supplier_name,
        supplier_vat=supplier_vat,
        references=_references(data.get("references"), document_type),
        metadata=metadata,
        confidence=0.99,
    )
    if not overrides.get("number") and data.get("number") not in (None, ""):
        doc.source_locators["number"] = {
            "locator_type": "JSON_POINTER",
            "pointer": "/number",
            "engine_id": "native-json-parser",
            "engine_version": "1",
        }
    if "currency" in data:
        doc.source_locators["currency"] = {
            "locator_type": "JSON_POINTER",
            "pointer": "/currency",
            "engine_id": "native-json-parser",
            "engine_version": "1",
        }

    for index, item in enumerate(lines, start=1):
        if not isinstance(item, dict):
            _structure_error("ogni elemento di lines deve essere un oggetto", line=index, field="lines", value=item)
        line_no = parse_integer_field(item.get("line_no"), field="line_no", line=index, default=index, minimum=1)
        provenance: dict[str, str] = {}
        quantity = parse_decimal_field(
            item.get("quantity"),
            field="quantity",
            line=line_no,
            required=True,
            provenance=provenance,
            max_decimal_places=4,
        )
        unit_price = parse_decimal_field(
            item.get("unit_price"),
            field="unit_price",
            line=line_no,
            required=document_type not in PRICE_OPTIONAL_TYPES,
            provenance=provenance,
            max_decimal_places=6,
        )
        base_quantity = parse_decimal_field(
            item.get("price_base_quantity"),
            field="price_base_quantity",
            line=line_no,
            default=1,
            provenance=provenance,
            missing_provenance="defaulted",
            max_decimal_places=4,
            exclusive_minimum=0,
        )
        discounts = _rates(item.get("discounts"), field="discounts", line=line_no, provenance=provenance)
        charges = _rates(item.get("charges"), field="charges", line=line_no, provenance=provenance)
        if discounts or charges:
            discount = effective_discount_rate(discounts, charges)
        else:
            discount = parse_decimal_field(
                item.get("discount_rate"),
                field="discount_rate",
                line=line_no,
                provenance=provenance,
                max_decimal_places=6,
                minimum=0,
                maximum=100,
            )
        tax = parse_decimal_field(
            item.get("tax_rate"),
            field="tax_rate",
            line=line_no,
            provenance=provenance,
            max_decimal_places=6,
            minimum=0,
            maximum=100,
        )
        expected = (quantity * unit_price / base_quantity) * (Decimal("1") - discount / Decimal("100"))
        if item.get("line_total") in (None, ""):
            line_total = expected
            provenance["line_total"] = "derived" if provenance.get("unit_price") == "source" else "missing"
        else:
            line_total = parse_decimal_field(
                item.get("line_total"),
                field="line_total",
                line=line_no,
                required=True,
                provenance=provenance,
                max_decimal_places=2,
            )
        raw = dict(item)
        raw["numeric_provenance"] = provenance
        if discounts:
            raw["discount_components"] = [str(value) for value in discounts]
        if charges:
            raw["charge_components"] = [str(value) for value in charges]
        doc.lines.append(
            ParsedLine(
                line_no=line_no,
                sku=item.get("sku"),
                description=item.get("description"),
                color=item.get("color"),
                size=item.get("size"),
                lot=item.get("lot"),
                unit_of_measure=item.get("unit_of_measure") or item.get("uom"),
                quantity=quantity,
                unit_price=unit_price,
                price_base_quantity=base_quantity,
                discount_rate=discount,
                tax_rate=tax,
                line_total=line_total,
                confidence=_parse_confidence(item.get("confidence"), line=line_no),
                raw=raw,
            )
        )
    return doc
