from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import ActivityProfile, DiscoveryRun, Document, RuleProposal, utcnow
from .normalizer import normalize_text

# The taxonomy is deliberately broad. It is evidence for a suggested profile, not a hard-coded lock-in.
_ACTIVITY_SIGNALS: dict[str, dict[str, Any]] = {
    "apparel": {
        "label": "Abbigliamento, calzature o tessile",
        "keywords": {
            "TAGLIA": 4,
            "SIZE": 4,
            "COLORE": 3,
            "COLOR": 3,
            "GIACCA": 3,
            "PANTALONE": 3,
            "MAGLIA": 3,
            "SCARPA": 3,
            "TESSUTO": 3,
            "COLLEZIONE": 2,
            "STAGIONE": 2,
        },
        "fields": {"size": 5, "color": 4},
    },
    "food": {
        "label": "Alimentare o bevande",
        "keywords": {
            "ALIMENTO": 3,
            "BEVANDA": 3,
            "KG": 2,
            "LITRO": 2,
            "SCADENZA": 5,
            "LOTTO": 4,
            "CONGELATO": 3,
            "BIO": 2,
            "INGREDIENTE": 3,
            "TEMPERATURA": 3,
        },
        "fields": {"lot": 4, "expiry": 6, "weight": 3, "volume": 3},
    },
    "automotive": {
        "label": "Automotive, ricambi o officina",
        "keywords": {
            "RICAMBIO": 4,
            "VEICOLO": 4,
            "AUTO": 2,
            "MOTORE": 3,
            "TELAIO": 5,
            "VIN": 6,
            "PNEUMATICO": 4,
            "FILTRO": 2,
            "FRENO": 3,
            "OEM": 4,
        },
        "fields": {"serial": 3, "vin": 7},
    },
    "construction": {
        "label": "Edilizia, ferramenta o materiali",
        "keywords": {
            "CANTIERE": 5,
            "EDILE": 4,
            "CEMENTO": 4,
            "MATTONELLA": 4,
            "ACCIAIO": 3,
            "METRO": 2,
            "MQ": 3,
            "M3": 3,
            "FERRAMENTA": 4,
            "PANNELLO": 2,
        },
        "fields": {"weight": 2, "unit": 2, "measure": 4},
    },
    "electronics": {
        "label": "Elettronica o apparecchiature",
        "keywords": {
            "SERIALE": 6,
            "SERIAL": 6,
            "IMEI": 7,
            "MODELLO": 2,
            "DISPOSITIVO": 4,
            "ELETTRONICO": 4,
            "BATTERIA": 3,
            "GARANZIA": 3,
        },
        "fields": {"serial": 7, "warranty": 4},
    },
    "pharma_health": {
        "label": "Farmaceutica, sanitaria o medicale",
        "keywords": {
            "FARMACO": 5,
            "MEDICALE": 4,
            "DISPOSITIVO MEDICO": 6,
            "DOSAGGIO": 5,
            "SCADENZA": 5,
            "LOTTO": 5,
            "PAZIENTE": 3,
            "STERILE": 4,
        },
        "fields": {"lot": 5, "expiry": 6, "dosage": 6},
    },
    "hospitality": {
        "label": "Ospitalità, ristorazione o strutture ricettive",
        "keywords": {
            "HOTEL": 5,
            "CAMERA": 4,
            "OSPITE": 4,
            "PERNOTTAMENTO": 5,
            "RISTORANTE": 4,
            "COPERTO": 3,
            "PRENOTAZIONE": 4,
            "SOGGIORNO": 4,
        },
        "fields": {"room": 6, "guest": 5, "service_period": 3},
    },
    "logistics": {
        "label": "Logistica, trasporto o distribuzione",
        "keywords": {
            "TRASPORTO": 5,
            "SPEDIZIONE": 5,
            "COLLO": 4,
            "PALLET": 4,
            "VETTORE": 5,
            "CONSEGNA": 2,
            "MAGAZZINO": 3,
            "PESO": 3,
        },
        "fields": {"weight": 4, "tracking": 6, "carrier": 5},
    },
    "industrial": {
        "label": "Produzione o forniture industriali",
        "keywords": {
            "INDUSTRIALE": 4,
            "COMPONENTE": 3,
            "MACCHINA": 3,
            "LAVORAZIONE": 4,
            "DISEGNO": 3,
            "TOLLERANZA": 5,
            "MATERIALE": 2,
            "LOTTO": 2,
        },
        "fields": {"lot": 2, "measure": 4, "material": 4},
    },
    "services": {
        "label": "Servizi professionali o manutenzione",
        "keywords": {
            "SERVIZIO": 3,
            "ORE": 5,
            "INTERVENTO": 4,
            "MANUTENZIONE": 4,
            "CONSULENZA": 4,
            "CANONE": 4,
            "PERIODO": 3,
            "TARIFFA": 4,
        },
        "fields": {"hours": 7, "service_period": 6, "rate": 5},
    },
}

_FIELD_FAMILIES: dict[str, set[str]] = {
    "expiry": {"EXPIRY", "EXPIRATION", "SCADENZA", "DATA SCADENZA", "BEST BEFORE", "USE BY"},
    "serial": {"SERIAL", "SERIAL NUMBER", "NUMERO SERIALE", "MATRICOLA", "IMEI"},
    "vin": {"VIN", "TELAIO", "NUMERO TELAIO"},
    "weight": {"WEIGHT", "PESO", "PESO NETTO", "PESO LORDO", "KG"},
    "volume": {"VOLUME", "LITRI", "LITRO", "ML"},
    "unit": {"UNIT", "UOM", "UNITA MISURA", "UNITA DI MISURA"},
    "measure": {"LUNGHEZZA", "ALTEZZA", "LARGHEZZA", "SPESSORE", "METRI", "MQ", "M3"},
    "hours": {"HOURS", "ORE", "ORE LAVORATE", "QUANTITA ORE"},
    "rate": {"RATE", "TARIFFA", "TARIFFA ORARIA"},
    "service_period": {"PERIODO", "DAL", "AL", "SERVICE PERIOD", "PERIODO SERVIZIO"},
    "tracking": {"TRACKING", "TRACKING NUMBER", "NUMERO SPEDIZIONE"},
    "carrier": {"CARRIER", "VETTORE", "TRASPORTATORE"},
    "warranty": {"WARRANTY", "GARANZIA", "SCADENZA GARANZIA"},
    "dosage": {"DOSAGE", "DOSAGGIO", "DOSE"},
    "room": {"ROOM", "CAMERA", "NUMERO CAMERA"},
    "guest": {"GUEST", "OSPITE", "NOME OSPITE"},
    "material": {"MATERIAL", "MATERIALE", "LEGA"},
}

_STANDARD_RAW_KEYS = {
    "LINE NO",
    "LINE NUMBER",
    "SKU",
    "CODE",
    "CODICE",
    "DESCRIPTION",
    "DESCRIZIONE",
    "COLOR",
    "COLORE",
    "SIZE",
    "TAGLIA",
    "LOT",
    "LOTTO",
    "QUANTITY",
    "QUANTITA",
    "UNIT PRICE",
    "PREZZO UNITARIO",
    "DISCOUNT RATE",
    "SCONTO",
    "TAX RATE",
    "IVA",
    "LINE TOTAL",
    "TOTALE RIGA",
}

_RULE_CATALOG: dict[str, tuple[str, str]] = {
    "line_total_mismatch": (
        "Controllo matematico delle righe",
        "Verifica quantità × prezzo × sconto rispetto al totale riga.",
    ),
    "duplicate_document_number": (
        "Numeri documento duplicati",
        "Segnala numeri documento ripetuti nella stessa operazione.",
    ),
    "duplicate_invoice_line": (
        "Righe fattura duplicate",
        "Cerca righe economicamente identiche ripetute nella stessa fattura.",
    ),
    "delivered_over_order": ("Consegne superiori all'ordine", "Confronta quantità ordinate e consegnate."),
    "invoiced_over_received": (
        "Fatturato superiore al verificato",
        "Confronta fatture con quantità ordinate o consegnate.",
    ),
    "price_over_order": (
        "Prezzo fatturato diverso dall'ordine",
        "Confronta il prezzo medio concordato con quello fatturato.",
    ),
    "discount_missing": ("Sconti mancanti", "Confronta gli sconti concordati con quelli applicati."),
    "currency_mismatch": ("Valute incoerenti", "Evita confronti economici diretti tra documenti in valute diverse."),
    "unit_mismatch": (
        "Unità di misura incompatibili",
        "Blocca confronti quantitativi o di prezzo tra unità non convertibili o mancanti.",
    ),
    "unmatched_invoice_line": (
        "Righe fattura non collegate",
        "Segnala costi o articoli senza riferimento in ordine o consegna.",
    ),
    "return_without_credit": ("Resi senza nota di credito", "Controlla che ogni reso trovi un accredito successivo."),
    "credit_below_return": ("Nota di credito insufficiente", "Confronta quantità rese e quantità accreditate."),
    "tax_rate_mismatch": ("Aliquota IVA incoerente", "Confronta l'aliquota fiscale della riga tra ordine e fattura."),
}


@dataclass
class DiscoverySettings:
    minimum_documents: int = 3
    auto_activate_threshold: float = 0.92
    confirmation_threshold: float = 0.68
    force_relearn: bool = False


def _flatten(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = normalize_text(str(key))
            path = f"{prefix}.{normalized_key}" if prefix else normalized_key
            yield from _flatten(item, path)
    elif isinstance(value, list):
        for item in value[:20]:
            yield from _flatten(item, prefix)
    elif value not in (None, ""):
        yield prefix, value


def _family_for_key(key: str) -> str | None:
    tail = key.split(".")[-1]
    if tail in _STANDARD_RAW_KEYS:
        return None
    for family, aliases in _FIELD_FAMILIES.items():
        if tail in aliases or any(alias in tail for alias in aliases if len(alias) >= 4):
            return family
    return None


def _json(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _activity_scores(corpus: str, field_coverage: dict[str, float]) -> dict[str, float]:
    tokens = normalize_text(corpus)
    scores: dict[str, float] = {}
    for activity, spec in _ACTIVITY_SIGNALS.items():
        score = 0.0
        for keyword, weight in spec["keywords"].items():
            occurrences = len(re.findall(rf"\b{re.escape(keyword)}\b", tokens))
            score += min(3, occurrences) * weight
        for field, weight in spec["fields"].items():
            score += field_coverage.get(field, 0.0) * weight * 5
        scores[activity] = score
    return scores


def _confidence_from_scores(scores: dict[str, float], document_count: int, line_count: int) -> tuple[str, float]:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ordered or ordered[0][1] <= 0:
        return "generic_commerce", min(0.55, 0.18 + math.log1p(document_count + line_count) / 12)
    best, best_score = ordered[0]
    second = ordered[1][1] if len(ordered) > 1 else 0.0
    separation = (best_score - second) / max(best_score, 1.0)
    evidence = min(1.0, math.log1p(document_count * 2 + line_count) / 5.2)
    confidence = min(0.99, 0.45 + separation * 0.32 + evidence * 0.22)
    return best, round(confidence, 4)


def _upsert_rule(
    db: Session,
    tenant_id: str,
    *,
    code: str,
    title: str,
    description: str,
    rationale: str,
    confidence: float,
    threshold: float,
    confirmation_threshold: float,
    parameters: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    source: str = "discovered",
    allow_auto_activate: bool = False,
) -> RuleProposal:
    proposal = db.scalar(
        select(RuleProposal).where(RuleProposal.tenant_id == tenant_id, RuleProposal.rule_code == code)
    )
    discovered_status = (
        "auto_active"
        if allow_auto_activate and confidence >= threshold
        else "needs_confirmation"
        if confidence >= confirmation_threshold
        else "inactive"
    )
    if proposal is None:
        proposal = RuleProposal(
            tenant_id=tenant_id,
            rule_code=code,
            title=title,
            description=description,
            rationale=rationale,
            confidence=confidence,
            status=discovered_status,
            parameters_json=json.dumps(parameters or {}, ensure_ascii=False),
            evidence_json=json.dumps(evidence or {}, ensure_ascii=False),
            source=source,
        )
        db.add(proposal)
    else:
        proposal.title = title
        proposal.description = description
        proposal.rationale = rationale
        proposal.confidence = confidence
        proposal.parameters_json = json.dumps(parameters or {}, ensure_ascii=False)
        proposal.evidence_json = json.dumps(evidence or {}, ensure_ascii=False)
        proposal.source = source
        # Explicit human decisions survive subsequent learning runs.
        if proposal.status not in {"confirmed", "rejected"}:
            proposal.status = discovered_status
    return proposal


def run_discovery(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    settings: DiscoverySettings | None = None,
) -> DiscoveryRun:
    cfg = settings or DiscoverySettings()
    run = DiscoveryRun(tenant_id=tenant_id, status="running", created_by=user_id)
    db.add(run)
    db.flush()
    try:
        documents = list(
            db.scalars(
                select(Document)
                .options(selectinload(Document.lines))
                .where(Document.tenant_id == tenant_id, Document.archived.is_(False), Document.parse_status == "parsed")
            )
        )
        lines = [line for document in documents for line in document.lines]
        run.document_count = len(documents)
        run.line_count = len(lines)

        field_counts: Counter[str] = Counter()
        raw_key_counts: Counter[str] = Counter()
        family_examples: dict[str, list[str]] = defaultdict(list)
        corpus_parts: list[str] = []
        roles_by_field: dict[str, set[str]] = defaultdict(set)

        for document in documents:
            corpus_parts.extend([document.source_filename, document.number or "", document.document_type])
            for line in document.lines:
                corpus_parts.extend(
                    [line.sku or "", line.description or "", line.color or "", line.size or "", line.lot or ""]
                )
                for field in (
                    "sku",
                    "description",
                    "color",
                    "size",
                    "lot",
                    "quantity",
                    "unit_price",
                    "discount_rate",
                    "tax_rate",
                ):
                    value = getattr(line, field)
                    if value not in (None, "", 0, 0.0):
                        field_counts[field] += 1
                raw = _json(line.raw_json)
                for key, value in _flatten(raw):
                    if not key:
                        continue
                    raw_key_counts[key] += 1
                    family = _family_for_key(key)
                    if family:
                        field_counts[family] += 1
                        roles_by_field[family].add(document.document_type)
                        if len(family_examples[family]) < 8:
                            family_examples[family].append(str(value)[:120])
                    if key.split(".")[-1] not in _STANDARD_RAW_KEYS:
                        corpus_parts.append(f"{key} {value}")

        denominator = max(1, len(lines))
        field_coverage = {key: min(1.0, count / denominator) for key, count in field_counts.items()}
        scores = _activity_scores(" ".join(corpus_parts), field_coverage)
        activity_type, activity_confidence = _confidence_from_scores(scores, len(documents), len(lines))
        activity_label = _ACTIVITY_SIGNALS.get(activity_type, {}).get("label", "Attività commerciale generica")
        enough_data = len(documents) >= cfg.minimum_documents and len(lines) >= max(2, cfg.minimum_documents)
        profile_status = (
            "ready"
            if enough_data and activity_confidence >= cfg.auto_activate_threshold
            else "needs_confirmation"
            if enough_data
            else "learning"
        )

        profile = db.scalar(select(ActivityProfile).where(ActivityProfile.tenant_id == tenant_id))
        if profile is None:
            profile = ActivityProfile(tenant_id=tenant_id)
            db.add(profile)
        if profile.human_confirmed and not cfg.force_relearn:
            activity_type = profile.activity_type
            activity_label = profile.activity_label
            activity_confidence = max(profile.confidence, 0.99)
            profile_status = "ready"
        else:
            if cfg.force_relearn:
                profile.human_confirmed = False
                profile.confirmed_by = None
                profile.confirmed_at = None
            profile.activity_type = activity_type
            profile.activity_label = activity_label
            profile.confidence = activity_confidence
            profile.status = profile_status
        profile.document_count = len(documents)
        profile.line_count = len(lines)
        profile.evidence_json = json.dumps(
            {"scores": scores, "top_terms": Counter(normalize_text(" ".join(corpus_parts)).split()).most_common(30)},
            ensure_ascii=False,
        )
        profile.field_profile_json = json.dumps(
            {
                "coverage": field_coverage,
                "raw_keys": raw_key_counts.most_common(80),
                "examples": family_examples,
                "roles": {key: sorted(value) for key, value in roles_by_field.items()},
            },
            ensure_ascii=False,
        )

        document_roles = Counter(document.document_type for document in documents)
        rule_specs: list[dict[str, Any]] = []

        def propose_builtin(code: str, confidence: float, rationale: str, evidence: dict[str, Any]) -> None:
            title, description = _RULE_CATALOG[code]
            rule_specs.append(
                {
                    "code": code,
                    "title": title,
                    "description": description,
                    "rationale": rationale,
                    "confidence": min(0.995, confidence),
                    "evidence": evidence,
                    "parameters": {},
                    "source": "built_in",
                }
            )

        # Universal arithmetic/integrity controls are safe when the relevant fields are present.
        propose_builtin(
            "line_total_mismatch",
            0.80 + min(0.19, field_coverage.get("quantity", 0) * 0.08 + field_coverage.get("unit_price", 0) * 0.11),
            "Quantità, prezzo e totale riga sono presenti nei documenti osservati.",
            {
                "quantity_coverage": field_coverage.get("quantity", 0),
                "price_coverage": field_coverage.get("unit_price", 0),
            },
        )
        propose_builtin(
            "duplicate_document_number",
            0.97 if len(documents) >= 2 else 0.65,
            "I documenti hanno identificativi confrontabili.",
            {"documents": len(documents)},
        )
        propose_builtin(
            "duplicate_invoice_line",
            0.96 if document_roles["invoice"] else 0.60,
            "Sono presenti fatture con righe confrontabili.",
            {"invoices": document_roles["invoice"]},
        )

        if document_roles["order"] and document_roles["delivery"]:
            propose_builtin(
                "delivered_over_order", 0.98, "Sono presenti sia ordini sia consegne.", dict(document_roles)
            )
        if document_roles["invoice"] and (document_roles["delivery"] or document_roles["order"]):
            propose_builtin(
                "invoiced_over_received",
                0.99 if document_roles["delivery"] else 0.91,
                "Le fatture possono essere confrontate con ordini o consegne.",
                dict(document_roles),
            )
            propose_builtin(
                "unmatched_invoice_line",
                0.92,
                "Le righe fattura possono essere ricondotte a documenti precedenti.",
                dict(document_roles),
            )
        if document_roles["invoice"] and document_roles["order"]:
            propose_builtin(
                "price_over_order", 0.98, "Ordini e fatture contengono prezzi unitari.", dict(document_roles)
            )
            discount_confidence = 0.70 + min(0.28, field_coverage.get("discount_rate", 0) * 0.35)
            propose_builtin(
                "discount_missing",
                discount_confidence,
                "Sono presenti sconti confrontabili tra ordine e fattura.",
                {"discount_coverage": field_coverage.get("discount_rate", 0)},
            )
            tax_confidence = 0.68 + min(0.30, field_coverage.get("tax_rate", 0) * 0.35)
            propose_builtin(
                "tax_rate_mismatch",
                tax_confidence,
                "Sono presenti aliquote fiscali su documenti confrontabili.",
                {"tax_coverage": field_coverage.get("tax_rate", 0)},
            )
        currencies = {document.currency for document in documents if document.currency}
        propose_builtin(
            "currency_mismatch",
            0.96 if len(currencies) > 1 else 0.84,
            "La valuta è un campo strutturato dei documenti.",
            {"currencies": sorted(currencies)},
        )
        if document_roles["return"]:
            propose_builtin(
                "return_without_credit",
                0.97,
                "Sono presenti documenti di reso: verificare l'accredito è una conseguenza diretta e non ambigua.",
                dict(document_roles),
            )
            propose_builtin(
                "credit_below_return",
                0.97 if document_roles["credit_note"] else 0.72,
                "Quantità rese e accreditate possono essere confrontate.",
                dict(document_roles),
            )

        # Any recurring non-standard field observed across at least two document roles becomes a generic consistency rule.
        for family, coverage in sorted(field_coverage.items()):
            if family in {
                "sku",
                "description",
                "color",
                "size",
                "lot",
                "quantity",
                "unit_price",
                "discount_rate",
                "tax_rate",
            }:
                continue
            roles = roles_by_field.get(family, set())
            if len(roles) < 2:
                continue
            confidence = min(0.97, 0.58 + coverage * 0.28 + min(0.12, len(roles) * 0.04))
            rule_specs.append(
                {
                    "code": f"field_consistency:{family}",
                    "title": f"Coerenza del campo {family}",
                    "description": f"Confronta automaticamente il campo '{family}' tra documenti collegati.",
                    "rationale": f"Il campo ricorre nel {coverage:.0%} delle righe ed è presente in {len(roles)} tipi di documento.",
                    "confidence": confidence,
                    "evidence": {
                        "coverage": coverage,
                        "roles": sorted(roles),
                        "examples": family_examples.get(family, []),
                    },
                    "parameters": {"family": family, "aliases": sorted(_FIELD_FAMILIES.get(family, {family.upper()}))},
                    "source": "discovered",
                }
            )

        proposals: list[RuleProposal] = []
        for spec in rule_specs:
            proposals.append(
                _upsert_rule(
                    db,
                    tenant_id,
                    code=spec["code"],
                    title=spec["title"],
                    description=spec["description"],
                    rationale=spec["rationale"],
                    confidence=round(spec["confidence"], 4),
                    threshold=cfg.auto_activate_threshold if enough_data else 1.01,
                    confirmation_threshold=cfg.confirmation_threshold,
                    parameters=spec["parameters"],
                    evidence=spec["evidence"],
                    source=spec["source"],
                    allow_auto_activate=spec["source"] == "built_in" and enough_data,
                )
            )
        db.flush()

        run.activity_type = activity_type
        run.activity_confidence = activity_confidence
        run.proposed_rules = len(proposals)
        run.auto_activated_rules = sum(1 for proposal in proposals if proposal.status in {"auto_active", "confirmed"})
        run.uncertain_rules = sum(1 for proposal in proposals if proposal.status == "needs_confirmation")
        run.details_json = json.dumps(
            {
                "activity_label": activity_label,
                "profile_status": profile_status,
                "field_coverage": field_coverage,
                "document_roles": dict(document_roles),
                "activation_policy": {
                    "built_in": "automatic only above threshold with sufficient data",
                    "discovered": "human confirmation required",
                },
                "questions": [
                    {"rule_id": proposal.id, "title": proposal.title, "confidence": proposal.confidence}
                    for proposal in proposals
                    if proposal.status == "needs_confirmation"
                ],
            },
            ensure_ascii=False,
        )
        run.status = "completed"
        run.completed_at = utcnow()
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_message = f"{type(exc).__name__}: {exc}"
        run.completed_at = utcnow()
        raise


def maybe_run_discovery(
    db: Session, tenant_id: str, user_id: str | None, *, minimum_documents: int = 3
) -> DiscoveryRun | None:
    document_count = int(
        db.scalar(
            select(func.count(Document.id)).where(
                Document.tenant_id == tenant_id,
                Document.archived.is_(False),
                Document.parse_status == "parsed",
            )
        )
        or 0
    )
    if document_count < minimum_documents:
        return None
    profile = db.scalar(select(ActivityProfile).where(ActivityProfile.tenant_id == tenant_id))
    if profile and profile.document_count == document_count:
        return None
    return run_discovery(db, tenant_id, user_id, DiscoverySettings(minimum_documents=minimum_documents))


def active_rule_codes(db: Session, tenant_id: str) -> set[str] | None:
    proposals = list(db.scalars(select(RuleProposal).where(RuleProposal.tenant_id == tenant_id)))
    if not proposals:
        return None
    return {proposal.rule_code for proposal in proposals if proposal.status in {"auto_active", "confirmed"}}
