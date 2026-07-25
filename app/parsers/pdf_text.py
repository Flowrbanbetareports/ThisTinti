from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

from .base import ParsedDocument, ParsedLine, ParseError, parse_date, parse_decimal_field


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


def parse_pdf(path: Path, overrides: dict) -> ParsedDocument:
    text, extraction_metadata, used_ocr = _extract_text(path)

    number_match = re.search(r"(?:NUMERO|N\.?|DOCUMENTO)\s*[:#-]?\s*([A-Z0-9/_-]{2,})", text, re.I)
    date_match = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b", text)
    base_confidence = 0.45 if used_ocr else 0.58
    doc = ParsedDocument(
        document_type=overrides.get("document_type"),
        number=overrides.get("number") or (number_match.group(1) if number_match else None),
        document_date=parse_date(overrides.get("document_date") or (date_match.group(1) if date_match else None)),
        supplier_name=overrides.get("supplier_name"),
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
                    "numeric_provenance": provenance,
                },
            )
        )
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
    elif used_ocr:
        doc.message = "Dati derivati da OCR locale: revisione umana raccomandata"
    return doc
