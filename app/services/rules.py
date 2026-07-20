from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    ChainDocument,
    DiscrepancyCase,
    Document,
    DocumentLine,
    EvidenceLink,
    OperationChain,
    RuleProposal,
)
from .line_matching import group_chain_lines
from .normalizer import normalize_text
from .units import canonical_unit_price, profiles_compatible, quantity_profile


@dataclass
class Finding:
    case_type: str
    severity: str
    amount: Decimal
    confidence: float
    title: str
    explanation: str
    action: str
    key: str
    evidence: list[dict]


def _documents(db: Session, chain: OperationChain, role: str) -> list[Document]:
    ids = list(
        db.scalars(
            select(ChainDocument.document_id)
            .where(
                ChainDocument.tenant_id == chain.tenant_id,
                ChainDocument.chain_id == chain.id,
                ChainDocument.role == role,
            )
            .order_by(ChainDocument.sequence_no)
        )
    )
    if not ids:
        primary_id = getattr(chain, f"{role}_document_id", None)
        ids = [primary_id] if primary_id else []
    if not ids:
        return []
    documents = list(db.scalars(select(Document).options(selectinload(Document.lines)).where(Document.id.in_(ids))))
    order = {doc_id: idx for idx, doc_id in enumerate(ids)}
    return sorted(documents, key=lambda doc: order.get(doc.id, 9999))


def _group(documents: list[Document]) -> dict[str, list[DocumentLine]]:
    grouped: dict[str, list[DocumentLine]] = defaultdict(list)
    for document in documents:
        for line in document.lines:
            grouped[line.canonical_key or f"line:{line.id}"].append(line)
    return grouped


ZERO = Decimal("0")
ONE = Decimal("1")
ONE_HUNDRED = Decimal("100")
QTY_EPSILON = Decimal("0.000001")
PRICE_EPSILON = Decimal("0.005")
RATE_EPSILON = Decimal("0.01")
MONEY_QUANTUM = Decimal("0.01")
ALWAYS_ON_RULES = {
    "currency_mismatch",
    "duplicate_document_number",
    "line_total_mismatch",
    "unit_mismatch",
    "duplicate_invoice_line",
    "payment_without_invoice",
    "payment_over_invoice",
    "duplicate_payment",
}


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def _qty(lines: list[DocumentLine]) -> Decimal:
    return sum((_decimal(x.quantity) for x in lines), ZERO)


def _source_unit_price(line: DocumentLine) -> Decimal:
    base = _decimal(getattr(line, "price_base_quantity", 1))
    return _decimal(line.unit_price) / (base if base else ONE)


def _normalized_unit_price(line: DocumentLine) -> Decimal:
    return canonical_unit_price(
        line.unit_price,
        getattr(line, "price_base_quantity", 1),
        line.unit_of_measure,
    )


def _canonical_abs_quantity(line: DocumentLine) -> Decimal:
    profile = quantity_profile([line])
    return abs(profile.quantity) if profile.compatible else abs(_decimal(line.quantity))


def _weighted_price(lines: list[DocumentLine]) -> Decimal:
    total_qty = sum((_canonical_abs_quantity(x) for x in lines), ZERO)
    if not total_qty:
        return ZERO
    return sum((_canonical_abs_quantity(x) * _normalized_unit_price(x) for x in lines), ZERO) / total_qty


def _discount(lines: list[DocumentLine]) -> Decimal:
    total_qty = sum((abs(_decimal(x.quantity)) for x in lines), ZERO)
    if not total_qty:
        return ZERO
    return sum((abs(_decimal(x.quantity)) * _decimal(x.discount_rate) for x in lines), ZERO) / total_qty


def _tax(lines: list[DocumentLine]) -> Decimal:
    total_qty = sum((abs(_decimal(x.quantity)) for x in lines), ZERO)
    if not total_qty:
        return ZERO
    return sum((abs(_decimal(x.quantity)) * _decimal(x.tax_rate) for x in lines), ZERO) / total_qty


def _money(value: Decimal | int | float | str) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _document_total(document: Document) -> Decimal:
    return _money(sum((abs(_decimal(line.line_total)) for line in document.lines), ZERO))


def _active_rule_proposals(db: Session, tenant_id: str) -> tuple[set[str] | None, list[RuleProposal]]:
    proposals = list(db.scalars(select(RuleProposal).where(RuleProposal.tenant_id == tenant_id)))
    if not proposals:
        return None, []
    active = {proposal.rule_code for proposal in proposals if proposal.status in {"auto_active", "confirmed"}}
    return active, [
        proposal
        for proposal in proposals
        if proposal.rule_code.startswith("field_consistency:") and proposal.rule_code in active
    ]


def _flatten_raw(value, prefix: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = normalize_text(str(key))
            path = f"{prefix}.{normalized_key}" if prefix else normalized_key
            yield from _flatten_raw(item, path)
    elif isinstance(value, list):
        for item in value[:20]:
            yield from _flatten_raw(item, prefix)
    elif value not in (None, ""):
        yield prefix, value


def _raw_family_values(line: DocumentLine, aliases: set[str]) -> list[str]:
    try:
        raw = json.loads(line.raw_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    values: list[str] = []
    for key, value in _flatten_raw(raw):
        tail = key.split(".")[-1]
        if tail in aliases or any(alias in tail for alias in aliases if len(alias) >= 4):
            normalized = normalize_text(str(value))
            if normalized:
                values.append(normalized)
    return list(dict.fromkeys(values))


def _dynamic_field_findings(
    grouped: dict[str, dict[str, list[DocumentLine]]], proposals: list[RuleProposal]
) -> list[Finding]:
    findings: list[Finding] = []
    all_keys = set().union(*(set(role_groups) for role_groups in grouped.values()))
    for proposal in proposals:
        family = proposal.rule_code.split(":", 1)[1]
        try:
            parameters = json.loads(proposal.parameters_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            parameters = {}
        aliases = {normalize_text(value) for value in parameters.get("aliases", [family]) if value}
        for canonical_key in sorted(all_keys):
            observations: list[tuple[str, DocumentLine, str]] = []
            for role in (
                "proposal",
                "order",
                "confirmation",
                "delivery",
                "invoice",
                "payment",
                "return",
                "credit_note",
            ):
                for line in grouped.get(role, {}).get(canonical_key, []):
                    for value in _raw_family_values(line, aliases):
                        observations.append((role, line, value))
            distinct = {value for _, _, value in observations}
            roles = {role for role, _, _ in observations}
            if len(distinct) <= 1 or len(roles) <= 1:
                continue
            first_role, first_line, first_value = observations[0]
            expected = next(
                (value for role, _, value in observations if role in {"proposal", "order", "confirmation"}),
                first_value,
            )
            observed = next(
                (value for role, _, value in observations if role in {"delivery", "invoice"} and value != expected),
                first_value,
            )
            observed_line = next((line for role, line, value in observations if value == observed), first_line)
            findings.append(
                Finding(
                    "field_consistency",
                    "medium",
                    0.0,
                    max(0.70, min(0.97, proposal.confidence)),
                    f"Campo {family} incoerente tra documenti",
                    f"Per la stessa riga commerciale sono stati rilevati valori differenti del campo '{family}': {', '.join(sorted(distinct))}.",
                    "Verificare il valore corretto e confermare o correggere la regola proposta.",
                    f"{family}:{canonical_key}",
                    [
                        _line_evidence(
                            observed_line, family, observed, expected, f"Regola auto-scoperta: {proposal.id}"
                        ),
                        _line_evidence(first_line, family, first_value, expected, f"Ruolo sorgente: {first_role}"),
                    ],
                )
            )
    return findings


def _fingerprint(chain_id: str, finding: Finding) -> str:
    return hashlib.sha256(f"{chain_id}|{finding.case_type}|{finding.key}".encode()).hexdigest()


def _line_evidence(line: DocumentLine | None, field: str, observed, expected, note: str | None = None) -> dict:
    return {
        "document_id": line.document_id if line else None,
        "document_line_id": line.id if line else None,
        "field_name": field,
        "observed_value": str(observed) if observed is not None else None,
        "expected_value": str(expected) if expected is not None else None,
        "note": note,
    }


def analyze_chain(db: Session, chain: OperationChain) -> list[DiscrepancyCase]:
    proposals = _documents(db, chain, "proposal")
    orders = _documents(db, chain, "order")
    confirmations = _documents(db, chain, "confirmation")
    deliveries = _documents(db, chain, "delivery")
    invoices = _documents(db, chain, "invoice")
    payments = _documents(db, chain, "payment")
    returns = _documents(db, chain, "return")
    credits = _documents(db, chain, "credit_note")

    grouped = group_chain_lines(
        db,
        chain,
        {
            "proposal": proposals,
            "order": orders,
            "confirmation": confirmations,
            "delivery": deliveries,
            "invoice": invoices,
            "payment": payments,
            "return": returns,
            "credit_note": credits,
        },
    )
    proposal_g = grouped["proposal"]
    order_g = grouped["order"]
    confirmation_g = grouped["confirmation"]
    commercial_g = confirmation_g if confirmations else order_g if orders else proposal_g
    commercial_role = "confirmation" if confirmations else "order" if orders else "proposal"
    commercial_label = "confermato" if confirmations else "ordinato" if orders else "proposto"
    delivery_g = grouped["delivery"]
    invoice_g = grouped["invoice"]
    return_g = grouped["return"]
    credit_g = grouped["credit_note"]
    findings: list[Finding] = []

    all_documents = proposals + orders + confirmations + deliveries + invoices + payments + returns + credits
    currencies = {d.currency for d in all_documents if d.currency}
    if len(currencies) > 1:
        findings.append(
            Finding(
                "currency_mismatch",
                "high",
                0.0,
                0.99,
                "Valute differenti nella stessa catena",
                f"La catena contiene più valute: {', '.join(sorted(currencies))}.",
                "Verificare il tasso di cambio e impedire confronti economici diretti non convertiti.",
                "chain-currency",
                [
                    {
                        "document_id": all_documents[0].id if all_documents else None,
                        "document_line_id": None,
                        "field_name": "currency",
                        "observed_value": ", ".join(sorted(currencies)),
                        "expected_value": "una sola valuta",
                        "note": None,
                    }
                ],
            )
        )

    for document in all_documents:
        seen_numbers = [
            d
            for d in all_documents
            if d.document_type == document.document_type and d.number and d.number == document.number
        ]
        if document.number and len(seen_numbers) > 1 and document.id == sorted(d.id for d in seen_numbers)[0]:
            findings.append(
                Finding(
                    "duplicate_document_number",
                    "high",
                    0.0,
                    0.97,
                    "Numero documento duplicato nella catena",
                    f"Il numero {document.number} compare {len(seen_numbers)} volte tra documenti di tipo {document.document_type}.",
                    "Verificare che non si tratti di un duplicato o di una revisione non identificata.",
                    f"duplicate-number:{document.document_type}:{document.number}",
                    [
                        {
                            "document_id": document.id,
                            "document_line_id": None,
                            "field_name": "number",
                            "observed_value": document.number,
                            "expected_value": "unico nella catena",
                            "note": None,
                        }
                    ],
                )
            )
        for line in document.lines:
            observed_total = _decimal(line.line_total)
            expected_total = (
                _decimal(line.quantity) * _source_unit_price(line) * (ONE - _decimal(line.discount_rate) / ONE_HUNDRED)
            )
            tolerance = max(Decimal("0.03"), abs(expected_total) * Decimal("0.005"))
            if abs(observed_total - expected_total) > tolerance:
                findings.append(
                    Finding(
                        "line_total_mismatch",
                        "medium",
                        _money(abs(observed_total - expected_total)),
                        0.88,
                        "Totale riga incoerente con quantità, prezzo e sconto",
                        f"Documento {document.number or document.source_filename}, riga {line.line_no}: totale {observed_total:.2f}, calcolo atteso {expected_total:.2f}.",
                        "Controllare arrotondamenti, maggiorazioni e formule del documento.",
                        f"line-total:{line.id}",
                        [_line_evidence(line, "line_total", f"{observed_total:.2f}", f"{expected_total:.2f}")],
                    )
                )

    all_keys = set(commercial_g) | set(delivery_g) | set(invoice_g)
    for key in sorted(all_keys):
        c = commercial_g.get(key, [])
        d = delivery_g.get(key, [])
        i = invoice_g.get(key, [])
        c_profile = quantity_profile(c)
        d_profile = quantity_profile(d)
        i_profile = quantity_profile(i)
        cq, dq, iq = c_profile.quantity, d_profile.quantity, i_profile.quantity
        cp, ip = _weighted_price(c), _weighted_price(i)
        cd, idis = _discount(c), _discount(i)
        ctax, itax = _tax(c), _tax(i)
        exemplar = (i or d or c)[0]
        label = exemplar.sku or exemplar.description or key

        relevant_profiles = [(commercial_role, c_profile), ("delivery", d_profile), ("invoice", i_profile)]
        incompatible_pairs = []
        for left_index, (left_role, left_profile) in enumerate(relevant_profiles):
            role_lines = {commercial_role: c, "delivery": d, "invoice": i}[left_role]
            if not role_lines:
                continue
            for right_role, right_profile in relevant_profiles[left_index + 1 :]:
                other_lines = {commercial_role: c, "delivery": d, "invoice": i}[right_role]
                if other_lines and not profiles_compatible(left_profile, right_profile):
                    incompatible_pairs.append((left_role, left_profile, right_role, right_profile))
        if incompatible_pairs:
            left_role, left_profile, right_role, right_profile = incompatible_pairs[0]
            findings.append(
                Finding(
                    "unit_mismatch",
                    "high",
                    ZERO,
                    0.99,
                    "Unità di misura incompatibili",
                    f"{label}: impossibile confrontare in modo affidabile {left_role} "
                    f"({', '.join(left_profile.source_units) or 'unità assente'}) e {right_role} "
                    f"({', '.join(right_profile.source_units) or 'unità assente'}).",
                    "Correggere o mappare le unità di misura prima di confrontare quantità e prezzi.",
                    key,
                    [
                        _line_evidence(
                            (c or d or i)[0],
                            "unit_of_measure",
                            ", ".join(left_profile.source_units) or None,
                            "unità compatibile",
                        ),
                        _line_evidence(
                            (i or d or c)[0],
                            "unit_of_measure",
                            ", ".join(right_profile.source_units) or None,
                            "unità compatibile",
                        ),
                    ],
                )
            )

        c_d_compatible = bool(c and d and profiles_compatible(c_profile, d_profile))
        c_i_compatible = bool(c and i and profiles_compatible(c_profile, i_profile))
        reference_lines = d if d else c
        reference_profile = d_profile if d else c_profile
        reference_i_compatible = bool(i and reference_lines and profiles_compatible(i_profile, reference_profile))

        if c_d_compatible and dq > cq + QTY_EPSILON:
            findings.append(
                Finding(
                    "delivered_over_order",
                    "medium",
                    max(ZERO, (dq - cq) * cp),
                    0.98,
                    "Quantità consegnata superiore all'ordine",
                    f"{label}: quantità {commercial_label} {cq:g}, consegnata complessivamente {dq:g}.",
                    "Verificare l'accettazione della consegna eccedente.",
                    key,
                    [
                        _line_evidence(d[0], "quantity_total", dq, cq),
                        _line_evidence(c[0], "quantity_total", cq, cq, f"Fonte: {commercial_role}"),
                    ],
                )
            )

        expected_for_invoice = reference_profile.quantity
        if reference_i_compatible and iq > expected_for_invoice + QTY_EPSILON:
            delta = iq - expected_for_invoice
            findings.append(
                Finding(
                    "invoiced_over_received",
                    "high",
                    max(ZERO, delta * ip),
                    0.99 if d else 0.91,
                    "Quantità fatturata superiore a quella verificata",
                    f"{label}: fatturate complessivamente {iq:g}, riferimento disponibile {expected_for_invoice:g}.",
                    "Controllare le righe e preparare una richiesta di rettifica.",
                    key,
                    [
                        _line_evidence(i[0], "quantity_total", iq, expected_for_invoice),
                        _line_evidence((d or c)[0], "quantity_total", expected_for_invoice, expected_for_invoice),
                    ],
                )
            )

        if c_i_compatible and ip > cp + PRICE_EPSILON:
            delta = ip - cp
            findings.append(
                Finding(
                    "price_over_order",
                    "high",
                    max(ZERO, min(iq or cq, cq or iq) * delta),
                    0.98,
                    "Prezzo fatturato superiore al riferimento commerciale",
                    f"{label}: prezzo medio {commercial_label} €{cp:.2f}, prezzo medio fattura €{ip:.2f}.",
                    "Verificare condizioni e sconti prima del pagamento.",
                    key,
                    [
                        _line_evidence(i[0], "unit_price", f"{ip:.4f}", f"{cp:.4f}"),
                        _line_evidence(c[0], "unit_price", f"{cp:.4f}", f"{cp:.4f}", f"Fonte: {commercial_role}"),
                    ],
                )
            )

        if i and c and cd > idis + RATE_EPSILON:
            gross = (iq or cq) * ip
            findings.append(
                Finding(
                    "discount_missing",
                    "high",
                    max(ZERO, gross * ((cd - idis) / ONE_HUNDRED)),
                    0.96,
                    "Sconto dell'ordine non applicato integralmente",
                    f"{label}: sconto medio {commercial_label} {cd:.2f}%, sconto medio fattura {idis:.2f}%.",
                    "Verificare la condizione commerciale e richiedere rettifica se confermata.",
                    key,
                    [
                        _line_evidence(i[0], "discount_rate", idis, cd),
                        _line_evidence(c[0], "discount_rate", cd, cd, f"Fonte: {commercial_role}"),
                    ],
                )
            )

        if i and c and abs(ctax - itax) > RATE_EPSILON:
            findings.append(
                Finding(
                    "tax_rate_mismatch",
                    "medium",
                    0.0,
                    0.94,
                    "Aliquota fiscale diversa tra ordine e fattura",
                    f"{label}: aliquota media {commercial_label} {ctax:.2f}%, aliquota media fattura {itax:.2f}%.",
                    "Verificare il trattamento fiscale prima della registrazione contabile.",
                    key,
                    [
                        _line_evidence(i[0], "tax_rate", itax, ctax),
                        _line_evidence(c[0], "tax_rate", ctax, ctax, f"Fonte: {commercial_role}"),
                    ],
                )
            )

        if i and not c and not d:
            desc = normalize_text(exemplar.description)
            is_fee = any(token in desc for token in ("TRASPORTO", "SPESA", "CONTRIBUTO", "IMBALLO", "FEE"))
            findings.append(
                Finding(
                    "unmatched_invoice_line",
                    "medium" if is_fee else "low",
                    abs(iq * ip),
                    0.72,
                    "Riga fattura senza corrispondenza",
                    f"{label}: nessuna riga equivalente trovata in ordine o consegne.",
                    "Collegare manualmente la riga o confermare che si tratti di un costo autorizzato.",
                    key,
                    [_line_evidence(i[0], "canonical_key", key, "riga collegata")],
                )
            )

    for invoice in invoices:
        seen: dict[tuple, DocumentLine] = {}
        for line in invoice.lines:
            signature = (
                line.canonical_key,
                quantity_profile([line]).quantity.quantize(Decimal("0.000001")),
                _normalized_unit_price(line).quantize(Decimal("0.000001")),
                _decimal(line.discount_rate).quantize(Decimal("0.0001")),
            )
            if signature in seen:
                findings.append(
                    Finding(
                        "duplicate_invoice_line",
                        "high",
                        abs(_decimal(line.line_total) or _decimal(line.quantity) * _normalized_unit_price(line)),
                        0.99,
                        "Possibile riga duplicata in fattura",
                        f"Nel documento {invoice.number or invoice.source_filename}, la riga {line.line_no} coincide con la riga {seen[signature].line_no}.",
                        "Verificare se la duplicazione è intenzionale.",
                        f"duplicate:{invoice.id}:{line.id}",
                        [
                            _line_evidence(line, "line_signature", signature, "unica"),
                            _line_evidence(seen[signature], "line_signature", signature, "unica"),
                        ],
                    )
                )
            else:
                seen[signature] = line

    invoice_total = sum((_document_total(document) for document in invoices), ZERO)
    payment_total = sum((_document_total(document) for document in payments), ZERO)
    if payments and not invoices:
        findings.append(
            Finding(
                "payment_without_invoice",
                "critical",
                payment_total,
                0.99,
                "Pagamento senza fattura collegata",
                f"Sono presenti pagamenti per €{payment_total:.2f} senza una fattura nella stessa catena.",
                "Bloccare la riconciliazione e identificare la fattura o la causale corretta.",
                "payment-without-invoice",
                [
                    {
                        "document_id": payments[0].id,
                        "document_line_id": None,
                        "field_name": "payment_total",
                        "observed_value": f"{payment_total:.2f}",
                        "expected_value": "fattura collegata",
                        "note": None,
                    }
                ],
            )
        )
    if invoices and payments and payment_total > invoice_total + Decimal("0.02"):
        findings.append(
            Finding(
                "payment_over_invoice",
                "critical",
                payment_total - invoice_total,
                0.99,
                "Pagamenti superiori al totale fatturato",
                f"Totale fatture €{invoice_total:.2f}; totale pagamenti €{payment_total:.2f}.",
                "Verificare duplicazioni, anticipi o attribuzioni errate prima di registrare il pagamento.",
                "payment-over-invoice",
                [
                    {
                        "document_id": payments[0].id,
                        "document_line_id": None,
                        "field_name": "payment_total",
                        "observed_value": f"{payment_total:.2f}",
                        "expected_value": f"{invoice_total:.2f}",
                        "note": None,
                    }
                ],
            )
        )
    payment_signatures: dict[tuple[str, Decimal], Document] = {}
    for payment in payments:
        try:
            references = json.loads(payment.references_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            references = {}
        invoice_refs = references.get("invoice_numbers") or []
        if isinstance(invoice_refs, str):
            invoice_refs = [invoice_refs]
        reference = "|".join(sorted(normalize_text(str(value)) for value in invoice_refs if value))
        if not reference:
            # Equal amounts alone are not sufficient evidence of a duplicate payment.
            continue
        signature = (reference, _document_total(payment))
        previous = payment_signatures.get(signature)
        if previous and signature[1] > ZERO:
            findings.append(
                Finding(
                    "duplicate_payment",
                    "critical",
                    signature[1],
                    0.98,
                    "Possibile doppio pagamento",
                    f"Due pagamenti distinti condividono riferimento e importo €{signature[1]:.2f}.",
                    "Verificare gli identificativi bancari o POS prima di contabilizzare il secondo pagamento.",
                    f"duplicate-payment:{previous.id}:{payment.id}",
                    [
                        {
                            "document_id": previous.id,
                            "document_line_id": None,
                            "field_name": "payment_signature",
                            "observed_value": f"{reference}|{signature[1]:.2f}",
                            "expected_value": "unico",
                            "note": None,
                        },
                        {
                            "document_id": payment.id,
                            "document_line_id": None,
                            "field_name": "payment_signature",
                            "observed_value": f"{reference}|{signature[1]:.2f}",
                            "expected_value": "unico",
                            "note": None,
                        },
                    ],
                )
            )
        else:
            payment_signatures[signature] = payment

    if returns:
        for key, rlines in return_g.items():
            clines = credit_g.get(key, [])
            return_profile = quantity_profile(rlines)
            credit_profile = quantity_profile(clines)
            rqty = abs(return_profile.quantity)
            cqty = abs(credit_profile.quantity)
            price = _weighted_price(rlines)
            exemplar = rlines[0]
            label = exemplar.sku or exemplar.description or key
            compatible_credit = not clines or profiles_compatible(return_profile, credit_profile)
            if clines and not compatible_credit:
                findings.append(
                    Finding(
                        "unit_mismatch",
                        "high",
                        ZERO,
                        0.99,
                        "Unità di misura incompatibili tra reso e accredito",
                        f"{label}: reso e nota di credito usano unità non confrontabili.",
                        "Correggere o mappare le unità prima di verificare l'accredito.",
                        f"return-credit:{key}",
                        [
                            _line_evidence(
                                rlines[0],
                                "unit_of_measure",
                                ", ".join(return_profile.source_units) or None,
                                "unità compatibile",
                            ),
                            _line_evidence(
                                clines[0],
                                "unit_of_measure",
                                ", ".join(credit_profile.source_units) or None,
                                "unità compatibile",
                            ),
                        ],
                    )
                )
            if not credits:
                findings.append(
                    Finding(
                        "return_without_credit",
                        "high",
                        rqty * price,
                        0.92,
                        "Reso senza nota di credito collegata",
                        f"{label}: reso complessivo di {rqty:g} unità senza nota di credito nella catena.",
                        "Verificare lo stato del reso e la nota di credito attesa.",
                        key,
                        [_line_evidence(exemplar, "credit_quantity", 0, rqty)],
                    )
                )
            elif compatible_credit and cqty + QTY_EPSILON < rqty:
                findings.append(
                    Finding(
                        "credit_below_return",
                        "high",
                        (rqty - cqty) * price,
                        0.97,
                        "Note di credito inferiori al reso",
                        f"{label}: reso complessivo {rqty:g}, accreditato complessivamente {cqty:g}.",
                        "Controllare le quantità e l'importo residuo.",
                        key,
                        [
                            _line_evidence(credit_g.get(key, [None])[0], "credit_quantity_total", cqty, rqty),
                            _line_evidence(exemplar, "return_quantity_total", rqty, rqty),
                        ],
                    )
                )

    active_rule_codes, dynamic_proposals = _active_rule_proposals(db, chain.tenant_id)
    findings.extend(_dynamic_field_findings(grouped, dynamic_proposals))
    if active_rule_codes is not None:
        findings = [
            finding
            for finding in findings
            if finding.case_type in ALWAYS_ON_RULES
            or finding.case_type in active_rule_codes
            or (
                finding.case_type == "field_consistency"
                and any(
                    finding.key.startswith(f"{proposal.rule_code.split(':', 1)[1]}:") for proposal in dynamic_proposals
                )
            )
        ]

    active_fingerprints: set[str] = set()
    output: list[DiscrepancyCase] = []
    for finding in findings:
        fp = _fingerprint(chain.id, finding)
        active_fingerprints.add(fp)
        case = db.scalar(
            select(DiscrepancyCase).where(
                DiscrepancyCase.tenant_id == chain.tenant_id,
                DiscrepancyCase.fingerprint == fp,
            )
        )
        if case is None:
            case = DiscrepancyCase(
                tenant_id=chain.tenant_id,
                chain_id=chain.id,
                fingerprint=fp,
                case_type=finding.case_type,
                severity=finding.severity,
                amount_estimate=_money(finding.amount),
                confidence=finding.confidence,
                title=finding.title,
                explanation=finding.explanation,
                recommended_action=finding.action,
            )
            db.add(case)
        else:
            case.case_type = finding.case_type
            case.severity = finding.severity
            case.amount_estimate = _money(finding.amount)
            case.confidence = finding.confidence
            case.title = finding.title
            case.explanation = finding.explanation
            case.recommended_action = finding.action
        if case.status in {"superseded", "open"}:
            case.status = "open" if finding.confidence >= 0.85 else "needs_review"
        db.flush()
        db.execute(delete(EvidenceLink).where(EvidenceLink.case_id == case.id))
        for evidence in finding.evidence:
            db.add(EvidenceLink(tenant_id=chain.tenant_id, case_id=case.id, **evidence))
        output.append(case)

    old_cases = list(
        db.scalars(
            select(DiscrepancyCase).where(
                DiscrepancyCase.tenant_id == chain.tenant_id,
                DiscrepancyCase.chain_id == chain.id,
                DiscrepancyCase.machine_generated.is_(True),
            )
        )
    )
    for case in old_cases:
        if case.fingerprint not in active_fingerprints and case.status in {"open", "needs_review"}:
            case.status = "superseded"

    chain.status = "review" if any(c.status in {"open", "needs_review"} for c in output) else "clear"
    db.flush()
    return output
