from pathlib import Path

from app.parsers.base import parse_file


def test_fatturapa_xml_parser(tmp_path: Path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <FatturaElettronica>
      <FatturaElettronicaHeader>
        <CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>01234567890</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>Supplier XML</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
      </FatturaElettronicaHeader>
      <FatturaElettronicaBody>
        <DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>2026-07-01</Data><Numero>INV-XML</Numero></DatiGeneraliDocumento><DatiOrdineAcquisto><IdDocumento>PO-XML</IdDocumento></DatiOrdineAcquisto></DatiGenerali>
        <DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><CodiceArticolo><CodiceTipo>SKU</CodiceTipo><CodiceValore>A-1</CodiceValore></CodiceArticolo><Descrizione>Giacca</Descrizione><Quantita>10</Quantita><PrezzoUnitario>20.00</PrezzoUnitario><ScontoMaggiorazione><Tipo>SC</Tipo><Percentuale>5.00</Percentuale></ScontoMaggiorazione><PrezzoTotale>190.00</PrezzoTotale><AliquotaIVA>22.00</AliquotaIVA></DettaglioLinee></DatiBeniServizi>
      </FatturaElettronicaBody>
    </FatturaElettronica>"""
    path = tmp_path / "invoice.xml"
    path.write_text(xml, encoding="utf-8")
    parsed = parse_file(path, path.name, "application/xml", {})
    assert parsed.document_type == "invoice"
    assert parsed.number == "INV-XML"
    assert parsed.supplier_name == "Supplier XML"
    assert parsed.references["order_numbers"] == ["PO-XML"]
    assert parsed.lines[0].line_total == 190.0


def test_xml_with_doctype_is_rejected(tmp_path: Path):
    xml = """<?xml version="1.0"?>
    <!DOCTYPE invoice [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <FatturaElettronica><Numero>&xxe;</Numero></FatturaElettronica>"""
    path = tmp_path / "danger.xml"
    path.write_text(xml, encoding="utf-8")
    from app.parsers import ParseError

    try:
        parse_file(path, path.name, "application/xml", {})
    except ParseError as exc:
        assert "DTD" in str(exc)
    else:
        raise AssertionError("DTD XML should have been rejected")
