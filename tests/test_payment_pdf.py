from decimal import Decimal

from app.parsers.pdf_text import _extract_payment_amount, parse_pdf


def test_payment_receipt_amount_parser_handles_italian_number_format():
    assert _extract_payment_amount("IMPORTO EUR 3.875,03") == Decimal("3875.03")
    assert _extract_payment_amount("TOTALE: € 200,00") == Decimal("200.00")


def test_payment_pdf_creates_economic_line_from_receipt(monkeypatch, tmp_path):
    receipt = """TRANSAZIONE ESEGUITA\n16/12/2025\nIMPORTO EUR 3.875,03\n"""
    monkeypatch.setattr(
        "app.parsers.pdf_text._extract_text",
        lambda _path: (receipt, {"extraction_method": "embedded_text", "pages": 1}, False),
    )
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.4")
    parsed = parse_pdf(path, {"document_type": "payment", "supplier_name": "Supplier"})
    assert parsed.lines[0].line_total == Decimal("3875.03")
    assert parsed.metadata["payment_amount"] == "3875.03"
    assert parsed.confidence == 0.76
