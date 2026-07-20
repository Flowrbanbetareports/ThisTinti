from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.parsers.base import parse_file


def test_ubl_peppol_invoice_parser(tmp_path: Path):
    path = tmp_path / "ubl-invoice.xml"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
 <cbc:CustomizationID>urn:cen.eu:en16931:2017</cbc:CustomizationID>
 <cbc:ID>UBL-42</cbc:ID><cbc:IssueDate>2026-07-19</cbc:IssueDate>
 <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
 <cac:OrderReference><cbc:ID>PO-42</cbc:ID></cac:OrderReference>
 <cac:AccountingSupplierParty><cac:Party>
  <cac:PartyName><cbc:Name>Supplier UBL</cbc:Name></cac:PartyName>
  <cac:PartyTaxScheme><cbc:CompanyID>IT01234567890</cbc:CompanyID></cac:PartyTaxScheme>
 </cac:Party></cac:AccountingSupplierParty>
 <cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="EA">10</cbc:InvoicedQuantity>
  <cbc:LineExtensionAmount currencyID="EUR">190.00</cbc:LineExtensionAmount>
  <cac:AllowanceCharge><cbc:ChargeIndicator>false</cbc:ChargeIndicator><cbc:MultiplierFactorNumeric>0.05</cbc:MultiplierFactorNumeric></cac:AllowanceCharge>
  <cac:Item><cbc:Description>Giacca tecnica</cbc:Description>
   <cac:SellersItemIdentification><cbc:ID>SKU-UBL-1</cbc:ID></cac:SellersItemIdentification>
   <cac:AdditionalItemProperty><cbc:Name>Colore</cbc:Name><cbc:Value>Navy</cbc:Value></cac:AdditionalItemProperty>
   <cac:AdditionalItemProperty><cbc:Name>Taglia</cbc:Name><cbc:Value>48</cbc:Value></cac:AdditionalItemProperty>
   <cac:ClassifiedTaxCategory><cbc:Percent>22</cbc:Percent></cac:ClassifiedTaxCategory>
  </cac:Item>
  <cac:Price><cbc:PriceAmount currencyID="EUR">20.00</cbc:PriceAmount></cac:Price>
 </cac:InvoiceLine>
</Invoice>""",
        encoding="utf-8",
    )
    result = parse_file(path, path.name, "application/xml", {})
    assert result.document_type == "invoice"
    assert result.number == "UBL-42"
    assert result.supplier_name == "Supplier UBL"
    assert result.supplier_vat == "IT01234567890"
    assert result.references["order_numbers"] == ["PO-42"]
    assert result.metadata["source"] == "ubl_xml"
    assert len(result.lines) == 1
    line = result.lines[0]
    assert line.sku == "SKU-UBL-1"
    assert line.quantity == 10
    assert line.unit_price == 20
    assert line.discount_rate == 5
    assert line.color == "Navy"
    assert line.size == "48"


@pytest.mark.skipif(
    not shutil.which("pdftoppm") or not shutil.which("tesseract"),
    reason="local OCR runtime unavailable",
)
def test_scanned_pdf_uses_local_ocr():
    path = Path(__file__).resolve().parents[1] / "samples" / "ocr_invoice.pdf"
    result = parse_file(path, path.name, "application/pdf", {"document_type": "invoice"})
    assert result.number == "INV-OCR-123"
    assert result.metadata["extraction_method"] == "local_ocr"
    assert result.metadata["evidence_class"] == "derived"
    assert result.message and "OCR" in result.message
    assert len(result.lines) == 1
    assert result.lines[0].sku == "SKU001"
    assert result.lines[0].quantity == 10
    assert result.lines[0].unit_price == 20
    assert result.lines[0].confidence < 0.7
