from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.parsers import pdf_text
from app.parsers.base import parse_file


def parse_text(monkeypatch, tmp_path: Path, text: str):
    monkeypatch.setattr(
        pdf_text,
        "_extract_text",
        lambda _path: (
            text,
            {"extraction_method": "local_ocr", "evidence_class": "derived", "ocr_pages": 1},
            True,
        ),
    )
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"placeholder")
    return parse_file(path, path.name, "application/pdf", {"document_type": "proposal"})


def test_pdf_semantics_prefers_strong_business_id_and_explicit_usd(monkeypatch, tmp_path: Path):
    text = """PEN-LINK
QUOTE
QUO-01487-5Z12C3
Currency: USD
1 COLLECTION MAINTENANCE - PREMIUM
1 XNET MAINTENANCE - PREMIUM
1 COLLECTION SUPPORT - PREMIUM
1 XNET SUPPORT - PREMIUM
$127,566.67 $127,566.67
$9,605.00 $9,605.00
$127,566.67 $127,566.67
$9,605.00 $9,605.00
"""
    result = parse_text(monkeypatch, tmp_path, text)
    assert result.number == "QUO-01487-5Z12C3"
    assert result.currency == "USD"
    assert len(result.lines) == 4
    assert result.metadata["document_number_recognition"]["status"] == "recognized"
    assert result.metadata["currency_recognition"]["status"] == "recognized"


def test_pdf_semantics_abstains_instead_of_inventing(monkeypatch, tmp_path: Path):
    result = parse_text(monkeypatch, tmp_path, "PEN-LINK DUTZ LINK\nNo reliable identifier here")
    assert result.number is None
    assert result.currency == "UNK"
    assert result.metadata["document_number_recognition"]["status"] == "abstained"
    assert result.metadata["currency_recognition"]["status"] == "abstained"


def test_pdf_semantics_abstains_on_bare_dollar_symbol(monkeypatch, tmp_path: Path):
    result = parse_text(monkeypatch, tmp_path, "QUOTE\nQUO-100-A1\n1 SERVICE $10.00 $10.00")
    assert result.currency == "UNK"
    assert result.metadata["currency_recognition"]["status"] == "abstained"
    assert result.metadata["currency_recognition"]["reason"] == "ambiguous_dollar_symbol"


def test_pdf_semantics_extracts_inline_business_rows(monkeypatch, tmp_path: Path):
    text = """QUOTE
QUO-04689-V8Y5D0
USD
1 MASTER DATABASE SERVER $10,607.80 $10,607.80
1 HARDWARE SHIPPING $106.08 $105.08
1 CONSULT - ONSITE SERVICES $3,500.00 $3,500.00
"""
    result = parse_text(monkeypatch, tmp_path, text)
    assert result.number == "QUO-04689-V8Y5D0"
    assert result.currency == "USD"
    assert len(result.lines) == 3
    assert result.lines[0].description == "MASTER DATABASE SERVER"
    assert result.lines[0].unit_price == Decimal("10607.80")


def test_pdf_semantics_discards_inconsistent_aligned_business_rows(monkeypatch, tmp_path: Path):
    text = """QUOTE
QUO-200-A2
USD
1 FIRST SERVICE
1 SECOND SERVICE
$10.00 $11.00
$20.00 $21.00
"""
    result = parse_text(monkeypatch, tmp_path, text)
    assert result.lines == []
    assert result.metadata["line_extraction_method"] == "abstained_ocr_alignment"
    assert result.metadata["discarded_ocr_aligned_rows"] == 2
    assert result.confidence <= 0.32
