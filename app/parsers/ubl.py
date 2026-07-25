from __future__ import annotations

from decimal import Decimal

from lxml import etree

from .base import (
    ParsedDocument,
    ParsedLine,
    ParseError,
    effective_discount_rate,
    parse_date,
    parse_decimal_field,
    parse_integer_field,
)

ROOT_TYPES = {
    "Invoice": "invoice",
    "CreditNote": "credit_note",
    "Order": "order",
    "OrderResponse": "confirmation",
    "DespatchAdvice": "delivery",
    "ReceiptAdvice": "delivery",
}

LINE_NAMES = {
    "invoice": "InvoiceLine",
    "credit_note": "CreditNoteLine",
    "order": "OrderLine",
    "confirmation": "OrderLine",
    "delivery": "DespatchLine",
}

QUANTITY_NAMES = (
    "InvoicedQuantity",
    "CreditedQuantity",
    "DeliveredQuantity",
    "ReceivedQuantity",
    "Quantity",
)


def _direct_node(node: etree._Element, name: str) -> etree._Element | None:
    values = node.xpath(f"./*[local-name()='{name}']")
    return values[0] if values else None


def _direct_text(node: etree._Element, name: str) -> str | None:
    target = _direct_node(node, name)
    return target.text.strip() if target is not None and target.text and target.text.strip() else None


def _first_text(node: etree._Element, path: str) -> str | None:
    values = node.xpath(path)
    return str(values[0]).strip() if values and str(values[0]).strip() else None


def _desc_text(node: etree._Element, name: str) -> str | None:
    return _first_text(node, f".//*[local-name()='{name}']/text()")


def _reference(root: etree._Element, container: str) -> str | None:
    return _first_text(root, f"./*[local-name()='{container}']/*[local-name()='ID']/text()")


def _supplier(root: etree._Element) -> tuple[str | None, str | None]:
    party = root.xpath("./*[local-name()='AccountingSupplierParty']/*[local-name()='Party']")
    if not party:
        party = root.xpath("./*[local-name()='SellerSupplierParty']/*[local-name()='Party']")
    if not party:
        return None, None
    node = party[0]
    name = _first_text(
        node,
        "./*[local-name()='PartyLegalEntity']/*[local-name()='RegistrationName']/text()",
    ) or _first_text(node, "./*[local-name()='PartyName']/*[local-name()='Name']/text()")
    vat = _first_text(
        node,
        "./*[local-name()='PartyTaxScheme']/*[local-name()='CompanyID']/text()",
    ) or _first_text(node, "./*[local-name()='PartyLegalEntity']/*[local-name()='CompanyID']/text()")
    return name, vat


def _item_properties(node: etree._Element) -> tuple[str | None, str | None, str | None]:
    color = size = lot = None
    for prop in node.xpath(".//*[local-name()='AdditionalItemProperty']"):
        key = (_direct_text(prop, "Name") or "").strip().upper()
        value = _direct_text(prop, "Value")
        if key in {"COLORE", "COLOR", "COLOUR", "COL"}:
            color = value
        elif key in {"TAGLIA", "SIZE", "TG"}:
            size = value
        elif key in {"LOTTO", "LOT", "BATCH"}:
            lot = value
    return color, size, lot


def parse_ubl_root(root: etree._Element, overrides: dict) -> ParsedDocument:
    root_name = etree.QName(root).localname
    detected = ROOT_TYPES.get(root_name)
    if not detected:
        raise ParseError(f"Documento UBL non supportato: {root_name}")

    supplier_name, supplier_vat = _supplier(root)
    doc = ParsedDocument(
        document_type=overrides.get("document_type") or detected,
        number=overrides.get("number") or _direct_text(root, "ID"),
        document_date=parse_date(overrides.get("document_date") or _direct_text(root, "IssueDate")),
        currency=(_direct_text(root, "DocumentCurrencyCode") or "EUR").upper(),
        supplier_name=overrides.get("supplier_name") or supplier_name,
        supplier_vat=supplier_vat,
        confidence=0.95,
        metadata={
            "source": "ubl_xml",
            "ubl_root_type": root_name,
            "ubl_customization_id": _direct_text(root, "CustomizationID"),
            "ubl_profile_id": _direct_text(root, "ProfileID"),
            "evidence_class": "source",
        },
    )

    references = {
        "order_numbers": _reference(root, "OrderReference"),
        "delivery_numbers": _reference(root, "DespatchDocumentReference"),
        "invoice_numbers": _reference(root, "InvoiceDocumentReference"),
        "contract_numbers": _reference(root, "ContractDocumentReference"),
    }
    for key, value in references.items():
        if value:
            doc.references[key] = [value]

    line_name = LINE_NAMES[detected]
    line_nodes = root.xpath(f".//*[local-name()='{line_name}']")
    for index, node in enumerate(line_nodes, start=1):
        # UBL OrderLine wraps commercial values inside LineItem.
        line_node = node
        line_items = node.xpath("./*[local-name()='LineItem']")
        if line_items:
            line_node = line_items[0]
        line_id = _direct_text(node, "ID") or str(index)
        line_no = (
            parse_integer_field(line_id, field="line_no", line=index, default=index, minimum=1)
            if line_id.strip().isdigit()
            else index
        )
        provenance: dict[str, str] = {}
        quantity_text = None
        unit_of_measure = None
        for quantity_name in QUANTITY_NAMES:
            quantity_node = _direct_node(line_node, quantity_name)
            if quantity_node is None:
                quantity_node = _direct_node(node, quantity_name)
            if quantity_node is not None and quantity_node.text is not None:
                quantity_text = quantity_node.text
                unit_of_measure = quantity_node.get("unitCode")
                break
        quantity = parse_decimal_field(
            quantity_text,
            field="quantity",
            line=line_no,
            required=True,
            provenance=provenance,
            max_decimal_places=8,
        )
        item = line_node.xpath("./*[local-name()='Item']") or node.xpath("./*[local-name()='Item']")
        item_node = item[0] if item else line_node
        sku = _first_text(
            item_node,
            ".//*[local-name()='SellersItemIdentification']/*[local-name()='ID']/text()",
        ) or _first_text(
            item_node,
            ".//*[local-name()='StandardItemIdentification']/*[local-name()='ID']/text()",
        )
        description = _desc_text(item_node, "Description") or _direct_text(item_node, "Name")
        price_node = _direct_node(line_node, "Price")
        if price_node is None:
            price_node = _direct_node(node, "Price")
        price = _direct_text(price_node, "PriceAmount") if price_node is not None else None
        unit_price = parse_decimal_field(
            price,
            field="unit_price",
            line=line_no,
            required=detected not in {"delivery"},
            provenance=provenance,
            max_decimal_places=10,
        )
        base_qty = parse_decimal_field(
            _direct_text(price_node, "BaseQuantity") if price_node is not None else None,
            field="price_base_quantity",
            line=line_no,
            default=1,
            provenance=provenance,
            missing_provenance="defaulted",
            max_decimal_places=8,
            exclusive_minimum=0,
        )
        tax = parse_decimal_field(
            _first_text(
                line_node,
                ".//*[local-name()='ClassifiedTaxCategory']/*[local-name()='Percent']/text()",
            )
            or _first_text(node, ".//*[local-name()='TaxCategory']/*[local-name()='Percent']/text()"),
            field="tax_rate",
            line=line_no,
            provenance=provenance,
            max_decimal_places=8,
            minimum=0,
            maximum=100,
        )
        discounts: list[Decimal] = []
        charges: list[Decimal] = []
        allowance_details: list[dict] = []
        unsupported_allowance_amount = False
        for allowance in line_node.xpath("./*[local-name()='AllowanceCharge']"):
            charge = (_direct_text(allowance, "ChargeIndicator") or "false").lower() == "true"
            percent_text = _direct_text(allowance, "MultiplierFactorNumeric")
            amount_text = _direct_text(allowance, "Amount")
            percent = parse_decimal_field(
                percent_text,
                field="charge_rate" if charge else "discount_rate",
                line=line_no,
                max_decimal_places=8,
                minimum=0,
            )
            if Decimal("0") < percent <= Decimal("1"):
                percent *= Decimal("100")
            if percent > Decimal("100"):
                raise ParseError(
                    f"Valore numerico fuori intervallo nel campo {'charge_rate' if charge else 'discount_rate'}: {percent_text}",
                    code="invalid_numeric_value",
                    line=line_no,
                    field="charge_rate" if charge else "discount_rate",
                    value=percent_text,
                    reason="Il valore percentuale deve essere compreso tra 0 e 100",
                )
            amount = parse_decimal_field(
                amount_text,
                field="charge_amount" if charge else "discount_amount",
                line=line_no,
                max_decimal_places=8,
                minimum=0,
            )
            if percent:
                (charges if charge else discounts).append(percent)
            elif amount:
                unsupported_allowance_amount = True
            allowance_details.append({"charge": charge, "percent": str(percent), "amount": str(amount)})
        discount = effective_discount_rate(discounts, charges)
        provenance["discount_rate"] = "derived" if discounts or charges else "missing"
        expected_total = quantity * unit_price / base_qty * (Decimal("1") - discount / Decimal("100"))
        line_total_text = _direct_text(line_node, "LineExtensionAmount") or _direct_text(node, "LineExtensionAmount")
        if line_total_text in (None, ""):
            line_total = expected_total
            provenance["line_total"] = "derived" if provenance.get("unit_price") == "source" else "missing"
        else:
            line_total = parse_decimal_field(
                line_total_text,
                field="line_total",
                line=line_no,
                required=True,
                provenance=provenance,
                max_decimal_places=8,
            )
        color, size, lot = _item_properties(item_node)
        doc.lines.append(
            ParsedLine(
                line_no=line_no,
                sku=sku,
                description=description,
                color=color,
                size=size,
                lot=lot,
                unit_of_measure=unit_of_measure,
                quantity=quantity,
                unit_price=unit_price,
                price_base_quantity=base_qty,
                discount_rate=discount,
                tax_rate=tax,
                line_total=line_total,
                confidence=0.96 if sku or description else 0.72,
                raw={
                    "source": "ubl_xml",
                    "ubl_line_type": line_name,
                    "discount_components": [str(value) for value in discounts],
                    "charge_components": [str(value) for value in charges],
                    "allowance_details": allowance_details,
                    "ubl_line_id": line_id,
                    "numeric_provenance": provenance,
                    "requires_allowance_review": unsupported_allowance_amount,
                },
            )
        )
        if unsupported_allowance_amount:
            doc.message = (
                "Sono presenti sconti o maggiorazioni UBL espressi soltanto come importo: "
                "verificare manualmente il calcolo della riga."
            )

    if not doc.lines:
        doc.confidence = 0.55
        doc.message = f"Metadati UBL {root_name} letti, ma nessuna riga {line_name} trovata"
    return doc
