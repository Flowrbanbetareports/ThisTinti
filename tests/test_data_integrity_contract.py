from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.parsers import ParseError, parse_file
from app.parsers.pdf_text import parse_pdf


def _upload_json(client, auth, payload, filename: str = "integrity.json"):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode("utf-8"), "application/json")},
    )


def _valid_payload() -> dict:
    return {
        "document_type": "invoice",
        "number": "INV-INTEGRITY-1",
        "supplier_name": "Integrity Supplier",
        "lines": [
            {
                "line_no": 1,
                "sku": "SKU-1",
                "quantity": 2,
                "unit_price": 10,
                "discount_rate": 0,
                "tax_rate": 22,
                "line_total": 20,
            }
        ],
    }


def _assert_numeric_error(response, *, field: str, value) -> None:
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_numeric_value"
    assert detail["document"] == "integrity.json"
    assert detail["line"] == 1
    assert detail["field"] == field
    assert detail["value"] == str(value)
    assert detail["reason"]
    assert detail["document_id"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity", "non-numero"),
        ("quantity", "NaN"),
        ("unit_price", "Infinity"),
        ("price_base_quantity", 0),
        ("discount_rate", "-Infinity"),
        ("tax_rate", "oops"),
        ("line_total", "NaN"),
        ("confidence", "Infinity"),
    ],
)
def test_invalid_json_numeric_values_return_structured_422_and_persist_failure(client, auth, field, value):
    payload = _valid_payload()
    payload["lines"][0][field] = value

    response = _upload_json(client, auth, payload)

    _assert_numeric_error(response, field=field, value=value)
    documents = client.get("/api/documents", headers=auth).json()
    assert len(documents) == 1
    assert documents[0]["parse_status"] == "failed"
    assert documents[0]["line_count"] == 0
    assert field in documents[0]["parse_message"]


@pytest.mark.parametrize("field", ["quantity", "unit_price"])
def test_missing_required_json_numeric_values_return_structured_422(client, auth, field):
    payload = _valid_payload()
    del payload["lines"][0][field]

    response = _upload_json(client, auth, payload)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "missing_numeric_value"
    assert detail["line"] == 1
    assert detail["field"] == field
    assert detail["value"] is None
    assert detail["document_id"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity", "1.23456"),
        ("unit_price", "1.2345678"),
        ("line_total", "1.234"),
    ],
)
def test_json_numeric_scale_is_enforced_without_rounding(client, auth, field, value):
    payload = _valid_payload()
    payload["lines"][0][field] = value

    response = _upload_json(client, auth, payload)

    _assert_numeric_error(response, field=field, value=value)
    assert "decimali" in response.json()["detail"]["reason"]


def test_documented_nested_supplier_and_legacy_reference_list_are_supported(client, auth):
    payload = _valid_payload()
    payload.pop("supplier_name")
    payload["supplier"] = {"name": "Nested Supplier", "vat_id": "IT01234567890"}
    payload["references"] = ["PO-LEGACY-1"]

    response = _upload_json(client, auth, payload)

    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["supplier"] == "Nested Supplier"
    assert document["parse_status"] == "parsed"


def test_documented_json_example_is_executable(client, auth):
    documentation = (Path(__file__).parents[1] / "docs" / "DATA_FORMATS.md").read_text(encoding="utf-8")
    section = documentation.split("## JSON strutturato", 1)[1]
    match = re.search(r"```json\s*(.*?)\s*```", section, re.DOTALL)
    assert match, "Esempio JSON documentato non trovato"
    payload = json.loads(match.group(1))

    response = _upload_json(client, auth, payload, filename="documented-example.json")

    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["supplier"] == "Fornitore Demo"
    assert document["lines"][0]["line_total"] == 386.4


def test_legacy_reference_list_on_root_document_is_preserved_without_matching_crash(client, auth):
    payload = _valid_payload()
    payload["document_type"] = "order"
    payload["references"] = ["LEGACY-ROOT"]

    response = _upload_json(client, auth, payload)

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"lines": []},
        {"document_type": "invoice", "lines": {}},
        {"document_type": "invoice", "lines": ["not-an-object"]},
        {"document_type": "not-supported", "lines": []},
        {"document_type": "invoice", "references": "PO-1", "lines": []},
        {"document_type": "invoice", "references": [None], "lines": []},
        {"document_type": "invoice", "references": {"order_numbers": [None]}, "lines": []},
        {"document_type": "invoice", "supplier": "Supplier", "lines": []},
        {"document_type": "invoice", "metadata": [], "lines": []},
        {"document_type": "invoice", "currency": [], "lines": []},
    ],
)
def test_invalid_json_shapes_return_422_instead_of_500(client, auth, payload):
    response = _upload_json(client, auth, payload)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_document_structure"
    assert detail["document"] == "integrity.json"
    assert detail["reason"]
    assert detail["document_id"]


def test_malformed_json_returns_structured_422(client, auth):
    response = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("broken.json", b"{not-json", "application/json")},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_document_structure"
    assert detail["document"] == "broken.json"
    assert detail["document_id"]


def test_optional_delivery_price_and_total_remain_null(client, auth):
    payload = {
        "document_type": "delivery",
        "number": "DDT-NO-PRICE",
        "supplier_name": "Integrity Supplier",
        "lines": [{"sku": "SKU-1", "quantity": 2}],
    }

    response = _upload_json(client, auth, payload)

    assert response.status_code == 201, response.text
    line = response.json()["document"]["lines"][0]
    assert line["unit_price"] is None
    assert line["line_total"] is None
    assert line["numeric_provenance"]["unit_price"] == "missing"
    assert line["numeric_provenance"]["line_total"] == "missing"
    chain = client.get("/api/chains", headers=auth).json()[0]
    detail = client.get(f"/api/chains/{chain['id']}", headers=auth).json()
    delivery = detail["comparison"]["rows"][0]["values"]["delivery"]
    assert delivery["unit_price"] is None
    assert delivery["line_total"] is None


def test_discount_and_charge_components_are_strict_and_traceable(client, auth):
    payload = _valid_payload()
    payload["lines"][0].pop("discount_rate")
    payload["lines"][0]["discounts"] = [10]
    payload["lines"][0]["charges"] = [5]
    payload["lines"][0]["line_total"] = 18.9

    response = _upload_json(client, auth, payload)

    assert response.status_code == 201, response.text
    line = response.json()["document"]["lines"][0]
    assert line["discount_rate"] == pytest.approx(5.5)
    assert line["numeric_provenance"]["discount_rate"] == "derived"


def test_missing_optional_numbers_are_explicit_and_not_serialized_as_zero(client, auth):
    payload = _valid_payload()
    line = payload["lines"][0]
    line.pop("discount_rate")
    line.pop("tax_rate")
    line.pop("line_total")

    response = _upload_json(client, auth, payload)

    assert response.status_code == 201, response.text
    parsed_line = response.json()["document"]["lines"][0]
    assert parsed_line["discount_rate"] is None
    assert parsed_line["tax_rate"] is None
    assert parsed_line["line_total"] == 20
    assert parsed_line["numeric_provenance"] == {
        "quantity": "source",
        "unit_price": "source",
        "price_base_quantity": "defaulted",
        "discount_rate": "missing",
        "tax_rate": "missing",
        "line_total": "derived",
    }


def test_batch_keeps_valid_member_and_reports_structured_parse_failure(client, auth):
    valid = _valid_payload()
    invalid = _valid_payload()
    invalid["number"] = "INV-INTEGRITY-BAD"
    invalid["lines"][0]["quantity"] = "NaN"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("valid.json", json.dumps(valid))
        archive.writestr("invalid.json", json.dumps(invalid))

    response = client.post(
        "/api/documents/batch",
        headers=auth,
        files={"file": ("integrity.zip", buffer.getvalue(), "application/zip")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["counts"]["ingested"] == 1
    assert body["counts"]["parse_failed"] == 1
    failed = next(item for item in body["results"] if item["filename"] == "invalid.json")
    assert failed["parse_status"] == "failed"
    assert failed["error"]["code"] == "invalid_numeric_value"
    assert failed["error"]["field"] == "quantity"
    assert failed["error"]["line"] == 1


def test_csv_invalid_numeric_value_is_not_coerced_to_zero(tmp_path: Path):
    path = tmp_path / "invalid.csv"
    path.write_text("SKU;QUANTITY;UNIT PRICE\nA-1;non-numero;10\n", encoding="utf-8")

    with pytest.raises(ParseError) as caught:
        parse_file(path, path.name, "text/csv", {"document_type": "order"})

    assert caught.value.code == "invalid_numeric_value"
    assert caught.value.line == 2
    assert caught.value.field == "quantity"
    assert caught.value.value == "non-numero"


def test_xlsx_invalid_numeric_value_is_not_coerced_to_zero(tmp_path: Path):
    path = tmp_path / "invalid.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["SKU", "QUANTITY", "UNIT PRICE"])
    sheet.append(["A-1", 1, "NaN"])
    workbook.save(path)

    with pytest.raises(ParseError) as caught:
        parse_file(
            path,
            path.name,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            {"document_type": "order"},
        )

    assert caught.value.code == "invalid_numeric_value"
    assert caught.value.line == 2
    assert caught.value.field == "unit_price"
    assert caught.value.value == "NaN"


def test_fatturapa_invalid_numeric_value_is_not_coerced_to_zero(tmp_path: Path):
    path = tmp_path / "invalid.xml"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <FatturaElettronica>
          <FatturaElettronicaBody>
            <DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Numero>INV-1</Numero></DatiGeneraliDocumento></DatiGenerali>
            <DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><Descrizione>Item</Descrizione><Quantita>NaN</Quantita><PrezzoUnitario>10</PrezzoUnitario><PrezzoTotale>10</PrezzoTotale></DettaglioLinee></DatiBeniServizi>
          </FatturaElettronicaBody>
        </FatturaElettronica>""",
        encoding="utf-8",
    )

    with pytest.raises(ParseError) as caught:
        parse_file(path, path.name, "application/xml", {})

    assert caught.value.code == "invalid_numeric_value"
    assert caught.value.line == 1
    assert caught.value.field == "quantity"
    assert caught.value.value == "NaN"


def test_ubl_invalid_numeric_value_is_not_coerced_to_zero(tmp_path: Path):
    path = tmp_path / "invalid-ubl.xml"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
          <ID>UBL-1</ID>
          <InvoiceLine>
            <ID>1</ID>
            <InvoicedQuantity>1</InvoicedQuantity>
            <LineExtensionAmount>10</LineExtensionAmount>
            <Price><PriceAmount>Infinity</PriceAmount></Price>
            <Item><Description>Item</Description></Item>
          </InvoiceLine>
        </Invoice>""",
        encoding="utf-8",
    )

    with pytest.raises(ParseError) as caught:
        parse_file(path, path.name, "application/xml", {})

    assert caught.value.code == "invalid_numeric_value"
    assert caught.value.line == 1
    assert caught.value.field == "unit_price"
    assert caught.value.value == "Infinity"


def test_pdf_malformed_numeric_row_is_not_shifted_or_coerced_to_zero(tmp_path: Path, monkeypatch):
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        "app.parsers.pdf_text._extract_text",
        lambda unused: (
            "A-1 ; Item ; non-numero ; 10.00 ; 0",
            {"extraction_method": "embedded_text", "pages": 1, "evidence_class": "source"},
            False,
        ),
    )

    with pytest.raises(ParseError) as caught:
        parse_pdf(path, {"document_type": "invoice"})

    assert caught.value.code == "invalid_numeric_value"
    assert caught.value.line == 1
    assert caught.value.field == "quantity"
    assert caught.value.value == "non-numero"


def test_p7m_uses_the_same_strict_numeric_validation_as_xml(tmp_path: Path, monkeypatch):
    path = tmp_path / "invalid.p7m"
    path.write_bytes(b"signed")
    xml = b"""<FatturaElettronica><FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento></DatiGeneraliDocumento></DatiGenerali><DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><Quantita>1</Quantita><PrezzoUnitario>oops</PrezzoUnitario></DettaglioLinee></DatiBeniServizi></FatturaElettronicaBody></FatturaElettronica>"""

    def fake_extract(unused_source: Path, output: Path) -> None:
        output.write_bytes(xml)

    monkeypatch.setattr("app.parsers.p7m._extract_cms", fake_extract)

    with pytest.raises(ParseError) as caught:
        parse_file(path, path.name, "application/pkcs7-mime", {})

    assert caught.value.code == "invalid_numeric_value"
    assert caught.value.field == "unit_price"
