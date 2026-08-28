from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
_MISSING = object()


class ParseError(ValueError):
    """A parsing failure with machine-readable source context."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "parse_error",
        line: int | None = None,
        field: str | None = None,
        value: Any = None,
        reason: str | None = None,
        document: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.line = line
        self.field = field
        self.value = value
        self.reason = reason or message
        self.document = document

    def with_document(self, document: str) -> ParseError:
        if not self.document:
            self.document = document
        return self

    def as_detail(self, *, document_id: str | None = None, document: str | None = None) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "document_id": document_id,
            "document": self.document or document,
            "line": self.line,
            "field": self.field,
            "value": None if self.value is None else str(self.value),
            "reason": self.reason,
        }


def _normalize_decimal_text(value: Any) -> str:
    text = str(value).strip().replace(" ", "")
    if text.count(",") == 1 and text.count(".") >= 1:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    return text


def safe_decimal(value: Any, default: Decimal | int | str = ZERO) -> Decimal:
    """Parse a finite decimal without silently replacing invalid input."""
    fallback = default if isinstance(default, Decimal) else Decimal(str(default))
    if value is None or value == "":
        return fallback
    if isinstance(value, bool):
        raise ParseError(
            f"Valore numerico non valido: {value}",
            code="invalid_numeric_value",
            value=value,
            reason="I valori booleani non sono numeri ammessi",
        )
    if isinstance(value, Decimal):
        result = value
    else:
        text = _normalize_decimal_text(value)
        try:
            result = Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise ParseError(
                f"Valore numerico non valido: {value}",
                code="invalid_numeric_value",
                value=value,
                reason="Il valore non è convertibile in un numero decimale",
            ) from exc
    if not result.is_finite():
        raise ParseError(
            f"Valore numerico non finito: {value}",
            code="invalid_numeric_value",
            value=value,
            reason="Il valore numerico non è finito (NaN o Infinity)",
        )
    return result


def parse_decimal_field(
    value: Any,
    *,
    field: str,
    line: int | None = None,
    required: bool = False,
    default: Decimal | int | str = ZERO,
    provenance: dict[str, str] | None = None,
    missing_provenance: str = "missing",
    max_decimal_places: int | None = None,
    max_integral_digits: int = 16,
    minimum: Decimal | int | str | None = None,
    maximum: Decimal | int | str | None = None,
    exclusive_minimum: Decimal | int | str | None = None,
) -> Decimal:
    """Parse one source field and preserve whether it was supplied or defaulted."""
    missing = value is None or value == ""
    if missing:
        if required:
            reason = "Il campo numerico obbligatorio non è presente"
            raise ParseError(
                f"Campo numerico mancante: {field}",
                code="missing_numeric_value",
                line=line,
                field=field,
                value=None,
                reason=reason,
            )
        if provenance is not None:
            provenance[field] = missing_provenance
        return default if isinstance(default, Decimal) else Decimal(str(default))

    try:
        result = safe_decimal(value, default)
    except ParseError as exc:
        raise ParseError(
            f"Valore numerico non valido nel campo {field}: {value}",
            code="invalid_numeric_value",
            line=line,
            field=field,
            value=value,
            reason=exc.reason,
        ) from exc

    normalized = result.normalize() if result else ZERO
    decimal_places = max(0, -normalized.as_tuple().exponent)
    if max_decimal_places is not None and decimal_places > max_decimal_places:
        reason = f"Sono ammessi al massimo {max_decimal_places} decimali"
        raise ParseError(
            f"Troppi decimali nel campo {field}: {value}",
            code="invalid_numeric_value",
            line=line,
            field=field,
            value=value,
            reason=reason,
        )

    integral_digits = max(1, result.copy_abs().adjusted() + 1) if result else 1
    if integral_digits > max_integral_digits:
        reason = f"Sono ammesse al massimo {max_integral_digits} cifre nella parte intera"
        raise ParseError(
            f"Valore numerico fuori intervallo nel campo {field}: {value}",
            code="invalid_numeric_value",
            line=line,
            field=field,
            value=value,
            reason=reason,
        )

    limits = (
        (minimum, result < safe_decimal(minimum) if minimum is not None else False, f"Il valore minimo è {minimum}"),
        (maximum, result > safe_decimal(maximum) if maximum is not None else False, f"Il valore massimo è {maximum}"),
        (
            exclusive_minimum,
            result <= safe_decimal(exclusive_minimum) if exclusive_minimum is not None else False,
            f"Il valore deve essere maggiore di {exclusive_minimum}",
        ),
    )
    for configured, invalid, reason in limits:
        if configured is not None and invalid:
            raise ParseError(
                f"Valore numerico fuori intervallo nel campo {field}: {value}",
                code="invalid_numeric_value",
                line=line,
                field=field,
                value=value,
                reason=reason,
            )

    if provenance is not None:
        provenance[field] = "source"
    return result


def safe_float(value: Any, default: float = 0.0) -> float:
    """Compatibility helper for non-monetary values such as line numbers/confidence."""
    return float(safe_decimal(value, Decimal(str(default))))


def parse_integer_field(
    value: Any,
    *,
    field: str,
    line: int | None = None,
    default: int | object = _MISSING,
    minimum: int | None = None,
) -> int:
    if value is None or value == "":
        if default is _MISSING:
            raise ParseError(
                f"Campo intero mancante: {field}",
                code="missing_numeric_value",
                line=line,
                field=field,
                value=None,
                reason="Il campo intero obbligatorio non è presente",
            )
        return int(default)
    parsed = parse_decimal_field(value, field=field, line=line, max_decimal_places=0)
    integer = int(parsed)
    if parsed != integer or (minimum is not None and integer < minimum):
        reason = "Il valore deve essere un numero intero"
        if minimum is not None:
            reason += f" maggiore o uguale a {minimum}"
        raise ParseError(
            f"Valore intero non valido nel campo {field}: {value}",
            code="invalid_numeric_value",
            line=line,
            field=field,
            value=value,
            reason=reason,
        )
    return integer


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
    source_locators: dict[str, dict[str, Any]] = field(default_factory=dict)
    lines: list[ParsedLine] = field(default_factory=list)
    confidence: float = 0.0
    message: str | None = None


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


def _postprocess_pdf_result(parsed: ParsedDocument) -> ParsedDocument:
    """Apply fail-closed guards to heuristic PDF-only recognizers."""
    recognition = parsed.metadata.get("currency_recognition")
    if isinstance(recognition, dict) and recognition.get("source") == "unambiguous_dollar_symbol":
        parsed.currency = "UNK"
        parsed.metadata["currency_recognition"] = {
            "status": "abstained",
            "reason": "ambiguous_dollar_symbol",
            "previous_source": "unambiguous_dollar_symbol",
        }

    aligned = [
        line
        for line in parsed.lines
        if isinstance(line.raw, dict) and line.raw.get("line_extraction_method") == "ocr_aligned_business_rows"
    ]
    if aligned:
        complete_alignment = len(aligned) == len(parsed.lines)
        totals_consistent = all(line.raw.get("line_total_consistent") is True for line in aligned)
        if complete_alignment and not totals_consistent:
            parsed.metadata["discarded_ocr_aligned_rows"] = len(aligned)
            parsed.metadata["line_extraction_method"] = "abstained_ocr_alignment"
            parsed.lines.clear()
            parsed.confidence = min(parsed.confidence, 0.32)
            parsed.message = "Righe OCR allineate scartate: i totali non supportano un abbinamento affidabile."
        else:
            for line in aligned:
                line.confidence = min(line.confidence, 0.55)
            parsed.metadata["aligned_rows_require_review"] = True
            parsed.confidence = min(parsed.confidence, 0.50)
            if not parsed.message:
                parsed.message = "Righe OCR allineate per posizione: revisione umana necessaria."
    return parsed


def parse_file(path: Path, filename: str, content_type: str | None, overrides: dict[str, Any]) -> ParsedDocument:
    try:
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

            return _postprocess_pdf_result(parse_pdf(path, overrides))
        if suffix == ".json":
            from .structured_json import parse_json

            return parse_json(path, overrides)
        raise ParseError(f"Formato non supportato: {suffix or content_type or filename}")
    except ParseError as exc:
        exc.with_document(filename)
        raise
