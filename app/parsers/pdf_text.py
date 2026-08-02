from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .base import ParsedDocument, ParsedLine, ParseError, parse_date, parse_decimal_field

CENT = Decimal("0.01")
TOTAL_TOLERANCE = Decimal("0.05")


def _extract_text(path: Path) -> tuple[str, dict[str, object], bool]:
    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ParseError(f"PDF non leggibile: {exc}") from exc
    if text.strip():
        return text, {"extraction_method": "embedded_text", "pages": page_count, "evidence_class": "source"}, False

    from .ocr import ocr_pdf

    text, metadata = ocr_pdf(path)
    metadata["source_pages"] = page_count
    return text, metadata, True


def _extract_payment_amount(text: str):
    """Extract a plausible receipt total without applying invoice-style heuristics."""
    patterns = (
        r"(?:IMPORTO|TOTALE|TOT\.?|PAGATO)\s*(?:EUR|EURO|€)?\s*[:=-]?\s*([0-9][0-9. ]*(?:,[0-9]{2}|\.[0-9]{2}))",
        r"(?:EUR|EURO|€)\s*([0-9][0-9. ]*(?:,[0-9]{2}|\.[0-9]{2}))",
    )
    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = parse_decimal_field(
                match.group(1),
                field="payment_amount",
                required=True,
                max_decimal_places=2,
            )
            if value > 0:
                candidates.append(value)
        if candidates:
            break
    return max(candidates) if candidates else None


def _normalize_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


LABEL_FIELDS = {
    "sku": {
        "sku",
        "codice",
        "codice articolo",
        "articolo",
        "item",
        "item code",
        "product code",
    },
    "description": {
        "descrizione",
        "descrizione articolo",
        "description",
        "product description",
    },
    "quantity": {
        "quantita",
        "qta",
        "qty",
        "quantity",
    },
    "unit_price": {
        "prezzo unitario",
        "prezzo",
        "unit price",
        "price",
    },
    "discount_rate": {
        "sconto",
        "discount",
    },
    "color": {
        "colore",
        "color",
    },
    "size": {
        "taglia",
        "size",
    },
    "line_total": {
        "totale riga",
        "totale",
        "line total",
        "amount",
    },
}
FIELD_BY_LABEL = {label: field for field, labels in LABEL_FIELDS.items() for label in labels}


def _labelled_value(line: str) -> tuple[str, str] | None:
    match = re.match(r"^\s*([^:=]{2,40})\s*[:=]\s*(.*?)\s*$", line)
    if not match:
        return None
    field = FIELD_BY_LABEL.get(_normalize_label(match.group(1)))
    value = match.group(2).strip()
    if not field or not value:
        return None
    return field, value


def _numeric_source(value: str, *, field: str, line: int) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"(?i)\b(?:EUR|EURO|USD|DOLLARI?)\b", " ", cleaned)
    cleaned = cleaned.replace("€", " ").replace("$", " ").replace("%", " ")
    cleaned = re.sub(r"\s+", "", cleaned)
    if not re.fullmatch(r"[+-]?[0-9][0-9.,]*", cleaned):
        raise ParseError(
            f"Valore numerico OCR non valido nel campo {field}: {value}",
            code="invalid_numeric_value",
            line=line,
            field=field,
            value=value,
            reason="Il valore etichettato contiene caratteri non numerici inattesi",
        )
    return cleaned


def _extract_labelled_reference(text: str, labels: tuple[str, ...]) -> str | None:
    for raw_line in text.splitlines():
        labelled = _labelled_value(raw_line)
        if labelled:
            continue
        match = re.match(r"^\s*([^:=]{2,50})\s*[:=]\s*(.*?)\s*$", raw_line)
        if not match:
            continue
        normalized = _normalize_label(match.group(1))
        if normalized in labels:
            value = match.group(2).strip()
            if re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{1,80}", value, re.I):
                return value
    return None


def _extract_supplier(text: str) -> str | None:
    for raw_line in text.splitlines():
        match = re.match(r"^\s*(?:FORNITORE|SUPPLIER)\s*[:=]\s*(.*?)\s*$", raw_line, re.I)
        if match:
            supplier = re.sub(r"\s+", " ", match.group(1)).strip()
            return supplier[:300] or None
    return None


def _build_labelled_line(
    fields: dict[str, str],
    *,
    source_line: int,
    used_ocr: bool,
    extraction_method: object,
) -> tuple[ParsedLine | None, dict[str, Any] | None]:
    sku = fields.get("sku")
    description = fields.get("description")
    if not (sku or description):
        return None, None
    if "quantity" not in fields or "unit_price" not in fields:
        return None, None

    provenance: dict[str, str] = {}
    quantity = parse_decimal_field(
        _numeric_source(fields["quantity"], field="quantity", line=source_line),
        field="quantity",
        line=source_line,
        required=True,
        provenance=provenance,
        max_decimal_places=4,
        exclusive_minimum=0,
    )
    price = parse_decimal_field(
        _numeric_source(fields["unit_price"], field="unit_price", line=source_line),
        field="unit_price",
        line=source_line,
        required=True,
        provenance=provenance,
        max_decimal_places=6,
        minimum=0,
    )
    discount = parse_decimal_field(
        _numeric_source(fields["discount_rate"], field="discount_rate", line=source_line)
        if fields.get("discount_rate")
        else None,
        field="discount_rate",
        line=source_line,
        provenance=provenance,
        max_decimal_places=6,
        minimum=0,
        maximum=100,
    )
    derived_total = quantity * price * (Decimal("1") - discount / Decimal("100"))
    source_total = None
    total_consistent = None
    total_delta = None
    if fields.get("line_total"):
        source_total = parse_decimal_field(
            _numeric_source(fields["line_total"], field="line_total", line=source_line),
            field="line_total",
            line=source_line,
            required=True,
            provenance=provenance,
            max_decimal_places=2,
            minimum=0,
        )
        total_delta = abs(source_total - derived_total)
        total_consistent = total_delta <= TOTAL_TOLERANCE
        provenance["line_total"] = "source_checked_against_derived"
    else:
        provenance["line_total"] = "derived"

    provenance.update(
        {
            "price_base_quantity": "defaulted",
            "tax_rate": "missing",
        }
    )
    confidence = Decimal("0.56") if used_ocr else Decimal("0.70")
    if not sku:
        confidence -= Decimal("0.08")
    if total_consistent is True:
        confidence += Decimal("0.03")
    elif total_consistent is False:
        confidence -= Decimal("0.12")
    confidence = max(Decimal("0.20"), min(confidence, Decimal("0.82")))

    warning = None
    if total_consistent is False:
        warning = {
            "source_line": source_line,
            "code": "line_total_mismatch",
            "source_total": str(source_total),
            "derived_total": str(derived_total.quantize(CENT)),
            "difference": str(total_delta.quantize(CENT)),
        }

    return (
        ParsedLine(
            line_no=source_line,
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=price,
            discount_rate=discount,
            color=fields.get("color"),
            size=fields.get("size"),
            line_total=derived_total,
            confidence=float(confidence),
            raw={
                "source_fields": dict(fields),
                "source_line_start": source_line,
                "extraction_method": extraction_method,
                "line_extraction_method": "labelled_fields",
                "source_line_total": None if source_total is None else str(source_total),
                "derived_line_total": str(derived_total),
                "line_total_consistent": total_consistent,
                "numeric_provenance": provenance,
            },
        ),
        warning,
    )


def _extract_labelled_lines(
    text: str,
    *,
    used_ocr: bool,
    extraction_method: object,
) -> tuple[list[ParsedLine], list[dict[str, Any]]]:
    lines: list[ParsedLine] = []
    warnings: list[dict[str, Any]] = []
    fields: dict[str, str] = {}
    source_line = 1

    def flush() -> None:
        nonlocal fields, source_line
        if not fields:
            return
        parsed, warning = _build_labelled_line(
            fields,
            source_line=source_line,
            used_ocr=used_ocr,
            extraction_method=extraction_method,
        )
        if parsed is not None:
            lines.append(parsed)
        if warning is not None:
            warnings.append(warning)
        fields = {}

    for index, raw_line in enumerate(text.splitlines(), start=1):
        labelled = _labelled_value(raw_line)
        if not labelled:
            continue
        field, value = labelled
        if field == "sku" and fields:
            flush()
        if not fields:
            source_line = index
        fields[field] = value
        if field == "line_total":
            flush()
    flush()
    return lines, warnings


def parse_pdf(path: Path, overrides: dict) -> ParsedDocument:
    text, extraction_metadata, used_ocr = _extract_text(path)

    number_match = re.search(r"(?:NUMERO|N\.?|DOCUMENTO)\s*[:#-]?\s*([A-Z0-9/_-]{2,})", text, re.I)
    date_match = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b", text)
    base_confidence = 0.45 if used_ocr else 0.58
    references: dict[str, list[str]] = {}
    order_reference = _extract_labelled_reference(
        text,
        (
            "riferimento ordine",
            "ordine riferimento",
            "order reference",
            "order no",
            "order number",
        ),
    )
    delivery_reference = _extract_labelled_reference(
        text,
        (
            "riferimento ddt",
            "riferimento consegna",
            "ddt riferimento",
            "delivery reference",
            "delivery no",
            "delivery number",
        ),
    )
    if order_reference:
        references["order_numbers"] = [order_reference]
    if delivery_reference:
        references["delivery_numbers"] = [delivery_reference]

    doc = ParsedDocument(
        document_type=overrides.get("document_type"),
        number=overrides.get("number") or (number_match.group(1) if number_match else None),
        document_date=parse_date(overrides.get("document_date") or (date_match.group(1) if date_match else None)),
        supplier_name=overrides.get("supplier_name") or _extract_supplier(text),
        references=references,
        confidence=base_confidence,
        metadata={**extraction_metadata, "text_preview": text[:1000]},
    )
    if not doc.document_type:
        raise ParseError("Per i PDF è necessario indicare il tipo documento")

    # Formato testuale supportato: SKU ; Descrizione ; Qta ; Prezzo ; Sconto ; Colore ; Taglia
    for idx, line in enumerate(text.splitlines(), start=1):
        parts = [part.strip() for part in re.split(r"\s*(?:;|\||\t)\s*", line.strip())]
        if len(parts) < 4 or len(parts) > 7:
            continue
        sku, desc, quantity_text, price_text, *optional = parts
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{1,}", sku, re.I):
            continue
        if quantity_text.strip().upper() in {"QTA", "QTY", "QUANTITA", "QUANTITY"}:
            continue
        discount_text = optional[0] if optional else None
        color = optional[1] if len(optional) > 1 else None
        size = optional[2] if len(optional) > 2 else None
        provenance: dict[str, str] = {}
        quantity = parse_decimal_field(
            quantity_text,
            field="quantity",
            line=idx,
            required=True,
            provenance=provenance,
            max_decimal_places=4,
        )
        price = parse_decimal_field(
            price_text,
            field="unit_price",
            line=idx,
            required=True,
            provenance=provenance,
            max_decimal_places=6,
        )
        discount = parse_decimal_field(
            discount_text,
            field="discount_rate",
            line=idx,
            provenance=provenance,
            max_decimal_places=6,
            minimum=0,
            maximum=100,
        )
        provenance.update(
            {
                "price_base_quantity": "defaulted",
                "tax_rate": "missing",
                "line_total": "derived",
            }
        )
        doc.lines.append(
            ParsedLine(
                line_no=idx,
                sku=sku,
                description=desc,
                quantity=quantity,
                unit_price=price,
                discount_rate=discount,
                color=color or None,
                size=size or None,
                line_total=quantity * price * (Decimal("1") - discount / Decimal("100")),
                confidence=0.58 if used_ocr else 0.72,
                raw={
                    "source_line": line,
                    "extraction_method": extraction_metadata["extraction_method"],
                    "line_extraction_method": "delimited_row",
                    "numeric_provenance": provenance,
                },
            )
        )

    labelled_warnings: list[dict[str, Any]] = []
    if not doc.lines and doc.document_type != "payment":
        labelled_lines, labelled_warnings = _extract_labelled_lines(
            text,
            used_ocr=used_ocr,
            extraction_method=extraction_metadata["extraction_method"],
        )
        doc.lines.extend(labelled_lines)
        if labelled_lines:
            doc.metadata["line_extraction_method"] = "labelled_fields"
            doc.metadata["labelled_line_count"] = len(labelled_lines)
        if labelled_warnings:
            doc.metadata["line_warnings"] = labelled_warnings

    if not doc.lines and doc.document_type == "payment":
        payment_amount = _extract_payment_amount(text)
        if payment_amount is not None:
            doc.lines.append(
                ParsedLine(
                    line_no=1,
                    sku="PAYMENT",
                    description="Pagamento rilevato dalla ricevuta",
                    quantity=Decimal("1"),
                    unit_price=payment_amount,
                    line_total=payment_amount,
                    confidence=0.56 if used_ocr else 0.76,
                    raw={
                        "extraction_method": extraction_metadata["extraction_method"],
                        "evidence": "receipt_total",
                        "numeric_provenance": {
                            "quantity": "defaulted",
                            "unit_price": "source",
                            "price_base_quantity": "defaulted",
                            "discount_rate": "missing",
                            "tax_rate": "missing",
                            "line_total": "source",
                        },
                    },
                )
            )
            doc.metadata["payment_amount"] = str(payment_amount)
            doc.message = (
                "Importo pagamento derivato da OCR locale: revisione umana raccomandata"
                if used_ocr
                else "Importo pagamento riconosciuto dalla ricevuta"
            )
            doc.confidence = 0.56 if used_ocr else 0.76

    if not doc.lines:
        doc.message = (
            "OCR eseguito; tabella righe non riconosciuta automaticamente"
            if used_ocr
            else "Metadati letti; tabella righe non riconosciuta automaticamente"
        )
        doc.confidence = 0.32 if used_ocr else 0.42
    elif labelled_warnings:
        doc.message = "Righe riconosciute, ma almeno un totale non coincide: revisione umana necessaria"
        doc.confidence = min(doc.confidence, 0.38 if used_ocr else 0.50)
    elif used_ocr:
        doc.message = "Dati derivati da OCR locale: revisione umana raccomandata"
        doc.confidence = max(doc.confidence, 0.55)
    return doc
