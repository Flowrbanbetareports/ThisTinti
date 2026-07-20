from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path
from typing import Any, Iterable

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


def safe_decimal(value: Any, default: Decimal | int | str = ZERO) -> Decimal:
    """Parse a finite decimal without passing through binary floating point."""
    fallback = default if isinstance(default, Decimal) else Decimal(str(default))
    if value is None or value == "":
        return fallback
    if isinstance(value, Decimal):
        return value if value.is_finite() else fallback
    if isinstance(value, float) and not math.isfinite(value):
        return fallback
    text = str(value).strip().replace(" ", "")
    if text.count(",") == 1 and text.count(".") >= 1:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        result = Decimal(text)
        return result if result.is_finite() else fallback
    except (InvalidOperation, ValueError):
        return fallback


def safe_float(value: Any, default: float = 0.0) -> float:
    """Compatibility helper for non-monetary values such as line numbers/confidence."""
    return float(safe_decimal(value, Decimal(str(default))))


def effective_discount_rate(
    discounts: Iterable[Decimal | int | float | str],
    charges: Iterable[Decimal | int | float | str] = (),
) -> Decimal:
    """Return the single equivalent percentage for sequential discounts and charges."""
    factor = Decimal("1")
    for value in discounts:
        rate = safe_decimal(value)
        factor *= Decimal("1") - (rate / ONE_HUNDRED)
    for value in charges:
        rate = safe_decimal(value)
        factor *= Decimal("1") + (rate / ONE_HUNDRED)
    return (Decimal("1") - factor) * ONE_HUNDRED


@dataclass
class ParsedLine:
    line_no: int
    sku: str | None = None
    description: str | None = None
    color: str | None = None
    size: str | None = None
    lot: str | None = None
    unit_of_measure: str | None = None
    quantity: Decimal = ZERO
    unit_price: Decimal = ZERO
    price_base_quantity: Decimal = Decimal("1")
    discount_rate: Decimal = ZERO
    tax_rate: Decimal = ZERO
    line_total: Decimal = ZERO
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    document_type: str | None = None
    number: str | None = None
    document_date: date | None = None
    currency: str = "EUR"
    supplier_name: str | None = None
    supplier_vat: str | None = None
    references: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    lines: list[ParsedLine] = field(default_factory=list)
    confidence: float = 0.0
    message: str | None = None


class ParseError(ValueError):
    pass


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    from datetime import datetime

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def parse_file(path: Path, filename: str, content_type: str | None, overrides: dict[str, Any]) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix == ".xml":
        from .xml_invoice import parse_xml

        return parse_xml(path, overrides)
    if suffix == ".p7m":
        from .p7m import parse_p7m

        return parse_p7m(path, overrides)
    if suffix in {".csv", ".xlsx", ".xlsm"}:
        from .tabular import parse_tabular

        return parse_tabular(path, overrides)
    if suffix == ".pdf":
        from .pdf_text import parse_pdf

        return parse_pdf(path, overrides)
    if suffix == ".json":
        from .structured_json import parse_json

        return parse_json(path, overrides)
    raise ParseError(f"Formato non supportato: {suffix or content_type or filename}")
