from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from .base import ParsedDocument, ParsedLine, ParseError, parse_date, safe_decimal


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
            value = safe_decimal(match.group(1))
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
    line_re = re.compile(
        r"^\s*([A-Z0-9][A-Z0-9._/-]{1,})\s*[;|\t]\s*(.*?)\s*[;|\t]\s*([\d.,]+)\s*[;|\t]\s*([\d.,]+)(?:\s*[;|\t]\s*([\d.,]+))?(?:\s*[;|\t]\s*([^;|\t]+))?(?:\s*[;|\t]\s*([^;|\t]+))?\s*$",
        re.I,
    )
    for idx, line in enumerate(text.splitlines(), start=1):
        match = line_re.match(line)
        if not match:
            continue
        sku, desc, qty, price, discount, color, size = match.groups()
        q = safe_decimal(qty)
        p = safe_decimal(price)
        disc = safe_decimal(discount)
        doc.lines.append(
            ParsedLine(
                line_no=idx,
                sku=sku,
                description=desc,
                quantity=q,
                unit_price=p,
                discount_rate=disc,
                color=color.strip() if color else None,
                size=size.strip() if size else None,
                line_total=q * p * (safe_decimal(1) - disc / safe_decimal(100)),
                confidence=0.58 if used_ocr else 0.72,
                raw={"source_line": line, "extraction_method": extraction_metadata["extraction_method"]},
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
                    quantity=safe_decimal(1),
                    unit_price=payment_amount,
                    line_total=payment_amount,
                    confidence=0.56 if used_ocr else 0.76,
                    raw={
                        "extraction_method": extraction_metadata["extraction_method"],
                        "evidence": "receipt_total",
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
