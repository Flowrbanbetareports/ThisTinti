import shutil
import subprocess
from pathlib import Path

import pytest

from app.parsers.base import parse_file


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL is required for P7M integration test")
def test_signed_fatturapa_p7m_is_extracted_and_parsed(tmp_path: Path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <FatturaElettronica>
      <FatturaElettronicaHeader>
        <CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>01234567890</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>Signed Supplier</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
      </FatturaElettronicaHeader>
      <FatturaElettronicaBody>
        <DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>2026-07-19</Data><Numero>INV-P7M</Numero></DatiGeneraliDocumento></DatiGenerali>
        <DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><CodiceArticolo><CodiceValore>P7M-1</CodiceValore></CodiceArticolo><Descrizione>Signed item</Descrizione><Quantita>2</Quantita><PrezzoUnitario>15.00</PrezzoUnitario><PrezzoTotale>30.00</PrezzoTotale><AliquotaIVA>22.00</AliquotaIVA></DettaglioLinee></DatiBeniServizi>
      </FatturaElettronicaBody>
    </FatturaElettronica>"""
    source = tmp_path / "invoice.xml"
    source.write_text(xml, encoding="utf-8")
    key = tmp_path / "key.pem"
    cert = tmp_path / "cert.pem"
    signed = tmp_path / "invoice.xml.p7m"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=ThisTinti Test",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "openssl",
            "cms",
            "-sign",
            "-binary",
            "-in",
            str(source),
            "-signer",
            str(cert),
            "-inkey",
            str(key),
            "-outform",
            "DER",
            "-out",
            str(signed),
            "-nosmimecap",
            "-nodetach",
        ],
        check=True,
        capture_output=True,
    )

    parsed = parse_file(signed, signed.name, "application/pkcs7-mime", {})
    assert parsed.number == "INV-P7M"
    assert parsed.supplier_name == "Signed Supplier"
    assert parsed.lines[0].sku == "P7M-1"
    assert parsed.metadata["signed_container"] == "CMS/PKCS#7"
    assert parsed.metadata["signature_integrity_checked"] is True
    assert parsed.metadata["certificate_trust_checked"] is False
