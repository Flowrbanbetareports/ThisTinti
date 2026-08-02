from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.parsers import ParseError
from app.parsers import pdf_text
from app.parsers.base import parse_file


def test_xlsx_parser(tmp_path: Path):
    path = tmp_path / "order.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Codice", "Descrizione", "Quantità", "Prezzo unitario", "Sconto", "Colore", "Taglia"])
    ws.append(["A-1", "Giacca", 10, 20, 5, "Blu", "48"])
    wb.save(path)
    result = parse_file(
        path,
        path.name,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        {"document_type": "order", "supplier_name": "Supplier"},
    )
    assert len(result.lines) == 1
    assert result.lines[0].quantity == 10
    assert result.lines[0].sku == "A-1"


def _mock_pdf_text(monkeypatch: pytest.MonkeyPatch, text: str, *, used_ocr: bool = True) -> None:
    metadata = {
        "extraction_method": "ocr" if used_ocr else "embedded_text",
        "pages": 1,
        "evidence_class": "derived" if used_ocr else "source",
    }
    monkeypatch.setattr(
        pdf_text,
        "_extract_text",
        lambda _path: (text, metadata.copy(), used_ocr),
    )


def test_pdf_ocr_extracts_conservative_labelled_line_and_references(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _mock_pdf_text(
        monkeypatch,
        """
FATTURA
Numero: INV-SCAN-001
Data: 01/08/2026
Fornitore: Fornitore Scan 01
Riferimento ordine: PO-SCAN-001
Riferimento DDT: DDT-SCAN-001

SKU: MAGLIA-001
Descrizione: Maglia cotone
Quantita: 10
Prezzo unitario: 12,50 EUR
Sconto: 0%
Totale: 125,00 EUR
""",
    )

    result = pdf_text.parse_pdf(tmp_path / "scan.pdf", {"document_type": "invoice"})

    assert result.number == "INV-SCAN-001"
    assert result.supplier_name == "Fornitore Scan 01"
    assert result.references == {
        "order_numbers": ["PO-SCAN-001"],
        "delivery_numbers": ["DDT-SCAN-001"],
    }
    assert result.message == "Dati derivati da OCR locale: revisione umana raccomandata"
    assert len(result.lines) == 1
    line = result.lines[0]
    assert line.sku == "MAGLIA-001"
    assert line.description == "Maglia cotone"
    assert line.quantity == Decimal("10")
    assert line.unit_price == Decimal("12.50")
    assert line.discount_rate == Decimal("0")
    assert line.line_total == Decimal("125.00")
    assert line.raw["line_extraction_method"] == "labelled_fields"
    assert line.raw["line_total_consistent"] is True
    assert result.metadata["labelled_line_count"] == 1


def test_pdf_ocr_labelled_numeric_value_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _mock_pdf_text(
        monkeypatch,
        """
Numero: INV-BAD-001
SKU: MAGLIA-001
Descrizione: Maglia cotone
Quantita: dieci
Prezzo unitario: 12,50 EUR
""",
    )

    with pytest.raises(ParseError) as exc_info:
        pdf_text.parse_pdf(tmp_path / "bad.pdf", {"document_type": "invoice"})

    assert exc_info.value.code == "invalid_numeric_value"
    assert exc_info.value.field == "quantity"
    assert exc_info.value.value == "dieci"
    assert exc_info.value.line == 3


def test_pdf_labelled_total_mismatch_requires_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _mock_pdf_text(
        monkeypatch,
        """
Numero: INV-MISMATCH-001
SKU: MAGLIA-001
Descrizione: Maglia cotone
Quantita: 10
Prezzo unitario: 12,50 EUR
Sconto: 0%
Totale: 130,00 EUR
""",
        used_ocr=False,
    )

    result = pdf_text.parse_pdf(tmp_path / "mismatch.pdf", {"document_type": "invoice"})

    assert len(result.lines) == 1
    assert result.lines[0].line_total == Decimal("125.00")
    assert result.lines[0].raw["source_line_total"] == "130.00"
    assert result.lines[0].raw["line_total_consistent"] is False
    assert result.message == "Righe riconosciute, ma almeno un totale non coincide: revisione umana necessaria"
    assert result.metadata["line_warnings"] == [
        {
            "source_line": 3,
            "code": "line_total_mismatch",
            "source_total": "130.00",
            "derived_total": "125.00",
            "difference": "5.00",
        }
    ]
