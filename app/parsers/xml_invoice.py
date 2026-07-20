from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from lxml import etree

from .base import (
    ParsedDocument,
    ParsedLine,
    ParseError,
    effective_discount_rate,
    parse_date,
    safe_decimal,
    safe_float,
)


def _local(node, name: str):
    result = node.xpath(f".//*[local-name()='{name}']")
    return result[0] if result else None


def _direct_text(node, name: str) -> str | None:
    values = node.xpath(f"./*[local-name()='{name}']/text()")
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _first_text(node, xpath: str) -> str | None:
    values = node.xpath(xpath)
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _texts(node, name: str) -> list[str]:
    return [str(x).strip() for x in node.xpath(f".//*[local-name()='{name}']/text()") if str(x).strip()]


def _text(node, name: str) -> str | None:
    vals = _texts(node, name)
    return vals[0] if vals else None


def _reference_details(root: etree._Element, container: str, id_field: str = "IdDocumento") -> list[dict]:
    details: list[dict] = []
    for node in root.xpath(f".//*[local-name()='{container}']"):
        identifier = _direct_text(node, id_field)
        if not identifier:
            continue
        line_refs = [
            str(value).strip()
            for value in node.xpath("./*[local-name()='RiferimentoNumeroLinea']/text()")
            if str(value).strip()
        ]
        details.append(
            {
                "type": container,
                "number": identifier,
                "date": _direct_text(node, "Data"),
                "line_numbers": line_refs,
                "item_code": _direct_text(node, "CodiceCommessaConvenzione"),
                "cup": _direct_text(node, "CodiceCUP"),
                "cig": _direct_text(node, "CodiceCIG"),
            }
        )
    return details


def _unique_numbers(details: list[dict]) -> list[str]:
    return list(dict.fromkeys(item["number"] for item in details if item.get("number")))


def parse_xml(path: Path, overrides: dict) -> ParsedDocument:
    try:
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False, recover=False
        )
        raw = path.read_bytes()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ParseError("XML con DTD o entità esterne non consentito")
        root = etree.fromstring(raw, parser=parser)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"XML non leggibile: {exc}") from exc

    root_name = etree.QName(root).localname
    if root_name in {"Invoice", "CreditNote", "Order", "OrderResponse", "DespatchAdvice", "ReceiptAdvice"}:
        from .ubl import parse_ubl_root

        return parse_ubl_root(root, overrides)

    tipo = _first_text(root, ".//*[local-name()='DatiGeneraliDocumento']/*[local-name()='TipoDocumento']/text()") or ""
    detected = "credit_note" if tipo.upper() in {"TD04", "TD08"} else "invoice"
    doc = ParsedDocument(
        document_type=overrides.get("document_type") or detected,
        number=overrides.get("number")
        or _first_text(root, ".//*[local-name()='DatiGeneraliDocumento']/*[local-name()='Numero']/text()"),
        document_date=parse_date(
            overrides.get("document_date")
            or _first_text(root, ".//*[local-name()='DatiGeneraliDocumento']/*[local-name()='Data']/text()")
        ),
        currency=(
            _first_text(root, ".//*[local-name()='DatiGeneraliDocumento']/*[local-name()='Divisa']/text()") or "EUR"
        ).upper(),
        confidence=0.96,
        metadata={"source": "fatturapa_xml", "fatturapa_document_type": tipo, "evidence_class": "source"},
    )

    supplier = root.xpath(".//*[local-name()='CedentePrestatore']")
    supplier_node = supplier[0] if supplier else root
    supplier_name = _first_text(supplier_node, ".//*[local-name()='Anagrafica']/*[local-name()='Denominazione']/text()")
    if not supplier_name:
        first = _first_text(supplier_node, ".//*[local-name()='Anagrafica']/*[local-name()='Nome']/text()") or ""
        last = _first_text(supplier_node, ".//*[local-name()='Anagrafica']/*[local-name()='Cognome']/text()") or ""
        supplier_name = f"{first} {last}".strip() or None
    doc.supplier_name = overrides.get("supplier_name") or supplier_name
    vat_country = _first_text(supplier_node, ".//*[local-name()='IdFiscaleIVA']/*[local-name()='IdPaese']/text()") or ""
    vat_code = _first_text(supplier_node, ".//*[local-name()='IdFiscaleIVA']/*[local-name()='IdCodice']/text()") or ""
    doc.supplier_vat = f"{vat_country}{vat_code}" if vat_code else None

    order_details = _reference_details(root, "DatiOrdineAcquisto")
    contract_details = _reference_details(root, "DatiContratto")
    convention_details = _reference_details(root, "DatiConvenzione")
    receipt_details = _reference_details(root, "DatiRicezione")
    invoice_details = _reference_details(root, "DatiFattureCollegate")
    delivery_details = _reference_details(root, "DatiDDT", id_field="NumeroDDT")

    if order_details:
        doc.references["order_numbers"] = _unique_numbers(order_details)
    if delivery_details:
        doc.references["delivery_numbers"] = _unique_numbers(delivery_details)
    if invoice_details:
        doc.references["invoice_numbers"] = _unique_numbers(invoice_details)
    reference_details = (
        order_details + contract_details + convention_details + receipt_details + invoice_details + delivery_details
    )
    if reference_details:
        doc.references["details"] = reference_details
    if contract_details:
        doc.references["contract_numbers"] = _unique_numbers(contract_details)
    if convention_details:
        doc.references["convention_numbers"] = _unique_numbers(convention_details)
    if receipt_details:
        doc.references["receipt_numbers"] = _unique_numbers(receipt_details)

    detail_nodes = root.xpath(".//*[local-name()='DettaglioLinee']")
    for index, node in enumerate(detail_nodes, start=1):
        codes = node.xpath("./*[local-name()='CodiceArticolo']/*[local-name()='CodiceValore']/text()")
        sku = str(codes[0]).strip() if codes else None
        description = _direct_text(node, "Descrizione")
        qty = safe_decimal(_direct_text(node, "Quantita"), 1)
        unit_price = safe_decimal(_direct_text(node, "PrezzoUnitario"))
        tax = safe_decimal(_direct_text(node, "AliquotaIVA"))
        discounts: list[Decimal] = []
        charges: list[Decimal] = []
        allowance_details: list[dict] = []
        for allowance in node.xpath("./*[local-name()='ScontoMaggiorazione']"):
            kind = (_direct_text(allowance, "Tipo") or "SC").upper()
            percent = safe_decimal(_direct_text(allowance, "Percentuale"))
            amount = safe_decimal(_direct_text(allowance, "Importo"))
            if percent:
                (charges if kind == "MG" else discounts).append(percent)
            allowance_details.append({"type": kind, "percent": str(percent), "amount": str(amount)})
        discount = effective_discount_rate(discounts, charges)
        expected_total = qty * unit_price * (Decimal("1") - discount / Decimal("100"))
        total = safe_decimal(_direct_text(node, "PrezzoTotale"), expected_total)
        color = None
        size = None
        lot = None
        other_data: dict[str, str] = {}
        for other in node.xpath("./*[local-name()='AltriDatiGestionali']"):
            key = (_direct_text(other, "TipoDato") or "").upper()
            value = _direct_text(other, "RiferimentoTesto") or _direct_text(other, "RiferimentoNumero")
            if key and value:
                other_data[key] = value
            if key in {"COLORE", "COLOR", "COL"}:
                color = value
            elif key in {"TAGLIA", "SIZE", "TG"}:
                size = value
            elif key in {"LOTTO", "LOT"}:
                lot = value
        doc.lines.append(
            ParsedLine(
                line_no=int(safe_float(_direct_text(node, "NumeroLinea"), index)),
                sku=sku,
                description=description,
                color=color,
                size=size,
                lot=lot,
                unit_of_measure=_direct_text(node, "UnitaMisura"),
                quantity=qty,
                unit_price=unit_price,
                discount_rate=discount,
                tax_rate=tax,
                line_total=total,
                confidence=0.97 if sku or description else 0.75,
                raw={
                    "source": "fatturapa_xml",
                    "discount_components": [str(value) for value in discounts],
                    "charge_components": [str(value) for value in charges],
                    "allowance_details": allowance_details,
                    "other_data": other_data,
                },
            )
        )

    if not doc.lines:
        doc.confidence = 0.55
        doc.message = "Metadati letti, ma nessuna riga DettaglioLinee trovata"
    return doc
