from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import zipfile
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..audit import add_audit
from ..config import settings
from ..models import (
    ChainDocument,
    DiscrepancyCase,
    Document,
    DocumentLine,
    OperationChain,
    ProcessingJob,
    ReviewDecision,
    Supplier,
    utcnow,
)
from ..rc15_models import (
    RC15CaseEconomicAssessment,
    RC15CompanyProfileVersion,
    RC15IntakeRecord,
    RC15PilotCase,
    RC15PilotWorkspace,
    RC15Practice,
)
from ..version import RELEASE_VERSION
from .ingestion import document_parse_error_detail
from .judgment_provenance import record_judgment_provenance, resolve_reviewer_identity


INTAKE_STATES = {"acquired", "review_required", "not_acquired", "blocked", "out_of_scope"}
INTAKE_CATEGORIES = {
    "ok",
    "degraded",
    "hostile",
    "out_of_scope",
    "parser_limit",
    "operator_input",
    "security_block",
}

DEFAULT_COMPANY_PROFILE: dict[str, Any] = {
    "default_currency": "EUR",
    "rounding_decimals": 2,
    "price_tolerance_percent": 1.0,
    "quantity_tolerance_percent": 0.0,
    "unit_aliases": {
        "pz": "PCE",
        "pezzi": "PCE",
        "piece": "PCE",
        "pieces": "PCE",
        "kg": "KGM",
        "g": "GRM",
        "m": "MTR",
        "cm": "CMT",
    },
    "significant_terms": [],
}

ROLE_ORDER = {
    "proposal": 0,
    "order": 1,
    "confirmation": 2,
    "delivery": 3,
    "invoice": 4,
    "payment": 5,
    "return": 6,
    "credit_note": 7,
}

_TOKEN_RE = re.compile(
    r"\b(?:\d+(?:[.,]\d+)?\s?(?:kw|w|kg|g|mm|cm|m|anni|anno|mesi|giorni|%|v|a)|[A-Z][A-Z0-9-]*\d[A-Z0-9-]*)\b",
    re.IGNORECASE,
)


def _json(value: str | None, default: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return default
    return parsed


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _money(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _within_storage(path: Path) -> bool:
    try:
        resolved = path.resolve()
        root = settings.storage_dir.resolve()
    except OSError:
        return False
    return resolved == root or root in resolved.parents


def _automatic_document_intake(document: Document) -> dict[str, Any]:
    if document.parse_status == "parsed":
        return {
            "state": "acquired",
            "category": "ok",
            "phase": "complete",
            "reason": "Documento acquisito e interpretato.",
            "automatic": True,
        }
    if document.parse_status == "review_required":
        return {
            "state": "review_required",
            "category": "degraded" if document.parse_message else "operator_input",
            "phase": "extraction",
            "reason": document.parse_message or "Documento acquisito con informazioni che richiedono verifica umana.",
            "automatic": True,
        }
    if document.parse_status == "failed":
        detail = document_parse_error_detail(document)
        reason = str(
            detail.get("reason") or detail.get("message") or document.parse_message or "Interpretazione fallita"
        )
        lowered = reason.casefold()
        if any(token in lowered for token in ("malware", "virus", "scanner di sicurezza", "security scan")):
            state, category, phase = "blocked", "security_block", "security"
        elif any(token in lowered for token in ("ocr", "scansion", "immagine", "raster")):
            state, category, phase = "not_acquired", "degraded", "ocr"
        elif any(token in lowered for token in ("non support", "unsupported", "fuori ambito")):
            state, category, phase = "out_of_scope", "out_of_scope", "classification"
        else:
            state, category, phase = "not_acquired", "parser_limit", "parsing"
        return {
            "state": state,
            "category": category,
            "phase": phase,
            "reason": reason,
            "automatic": True,
            "error": detail,
        }
    return {
        "state": "review_required",
        "category": "operator_input",
        "phase": "processing",
        "reason": document.parse_message or f"Stato tecnico: {document.parse_status}",
        "automatic": True,
    }


def _automatic_job_intake(job: ProcessingJob) -> dict[str, Any]:
    reason = job.error_message or "Processo di acquisizione non completato"
    lowered = reason.casefold()
    if any(token in lowered for token in ("malware", "virus", "clam", "scanner")):
        state, category, phase = "blocked", "security_block", "security"
    elif any(token in lowered for token in ("unsupported", "non support", "format")):
        state, category, phase = "out_of_scope", "out_of_scope", "classification"
    elif "ocr" in lowered or "scansion" in lowered:
        state, category, phase = "not_acquired", "degraded", "ocr"
    else:
        state, category, phase = "not_acquired", "parser_limit", "processing"
    return {"state": state, "category": category, "phase": phase, "reason": reason, "automatic": True}


def _intake_record_payload(record: RC15IntakeRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "id": record.id,
        "state": record.state,
        "category": record.category,
        "phase": record.phase,
        "reason": record.reason,
        "note": record.note,
        "automatic": record.automatic,
        "retry_count": record.retry_count,
        "last_retry_at": record.last_retry_at.isoformat() if record.last_retry_at else None,
        "updated_at": record.updated_at.isoformat(),
    }


def list_intake(db: Session, tenant_id: str, *, include_success: bool = True) -> list[dict[str, Any]]:
    records = {
        (item.subject_type, item.subject_id): item
        for item in db.scalars(select(RC15IntakeRecord).where(RC15IntakeRecord.tenant_id == tenant_id))
    }
    documents = list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.lines))
            .where(Document.tenant_id == tenant_id, Document.archived.is_(False))
            .order_by(Document.created_at.desc())
        )
    )
    supplier_ids = {item.supplier_id for item in documents if item.supplier_id}
    suppliers = (
        {item.id: item for item in db.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))}
        if supplier_ids
        else {}
    )
    output: list[dict[str, Any]] = []
    linked_job_document_ids: set[str] = set()
    for document in documents:
        automatic = _automatic_document_intake(document)
        explicit = records.get(("document", document.id))
        classification = _intake_record_payload(explicit) or automatic
        if not include_success and classification["state"] == "acquired":
            continue
        output.append(
            {
                "subject_type": "document",
                "subject_id": document.id,
                "document_id": document.id,
                "job_id": None,
                "filename": document.source_filename,
                "document_type": document.document_type,
                "supplier": suppliers.get(document.supplier_id).legal_name
                if document.supplier_id in suppliers
                else None,
                "parse_status": document.parse_status,
                "confidence": float(document.confidence or 0),
                "file_available": Path(document.storage_path).is_file(),
                "created_at": document.created_at.isoformat(),
                "classification": classification,
                "can_retry": Path(document.storage_path).is_file()
                and document.parse_status in {"failed", "review_required"},
            }
        )

    failed_jobs = list(
        db.scalars(
            select(ProcessingJob)
            .where(
                ProcessingJob.tenant_id == tenant_id,
                ProcessingJob.job_type.in_(("ingest_document", "ingest_batch")),
                ProcessingJob.status == "failed",
            )
            .order_by(ProcessingJob.created_at.desc())
        )
    )
    for job in failed_jobs:
        payload = _json(job.input_json, {})
        result = _json(job.result_json, {})
        document_id = str(result.get("document_id") or "")
        if document_id:
            linked_job_document_ids.add(document_id)
            continue
        explicit = records.get(("job", job.id))
        classification = _intake_record_payload(explicit) or _automatic_job_intake(job)
        output.append(
            {
                "subject_type": "job",
                "subject_id": job.id,
                "document_id": None,
                "job_id": job.id,
                "filename": payload.get("original_filename") or payload.get("filename") or "Acquisizione",
                "document_type": (payload.get("overrides") or {}).get("document_type"),
                "supplier": (payload.get("overrides") or {}).get("supplier_name"),
                "parse_status": "failed",
                "confidence": 0.0,
                "file_available": bool(payload.get("rejected_path") or payload.get("staged_path")),
                "created_at": job.created_at.isoformat(),
                "classification": classification,
                "can_retry": True,
            }
        )
    return sorted(output, key=lambda item: item["created_at"], reverse=True)


def classify_intake(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    *,
    subject_type: str,
    subject_id: str,
    state: str,
    category: str,
    phase: str | None,
    reason: str,
    note: str | None,
) -> RC15IntakeRecord:
    if subject_type not in {"document", "job"}:
        raise ValueError("Tipo di elemento non valido")
    if state not in INTAKE_STATES or category not in INTAKE_CATEGORIES:
        raise ValueError("Classificazione di acquisizione non valida")
    exists = (
        db.scalar(select(Document.id).where(Document.id == subject_id, Document.tenant_id == tenant_id))
        if subject_type == "document"
        else db.scalar(
            select(ProcessingJob.id).where(ProcessingJob.id == subject_id, ProcessingJob.tenant_id == tenant_id)
        )
    )
    if not exists:
        raise LookupError("Elemento di acquisizione non trovato")
    record = db.scalar(
        select(RC15IntakeRecord).where(
            RC15IntakeRecord.tenant_id == tenant_id,
            RC15IntakeRecord.subject_type == subject_type,
            RC15IntakeRecord.subject_id == subject_id,
        )
    )
    if record is None:
        record = RC15IntakeRecord(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
            state=state,
            category=category,
            phase=phase,
            reason=reason.strip(),
            note=note.strip() if note else None,
            automatic=False,
            classified_by=user_id,
        )
        db.add(record)
    else:
        record.state = state
        record.category = category
        record.phase = phase
        record.reason = reason.strip()
        record.note = note.strip() if note else None
        record.automatic = False
        record.classified_by = user_id
        record.updated_at = utcnow()
    add_audit(
        db,
        tenant_id,
        "rc15.intake_classified",
        user_id,
        subject_type,
        subject_id,
        {"state": state, "category": category, "phase": phase, "note": note},
    )
    db.flush()
    return record


def record_document_retry(db: Session, tenant_id: str, document_id: str) -> None:
    record = db.scalar(
        select(RC15IntakeRecord).where(
            RC15IntakeRecord.tenant_id == tenant_id,
            RC15IntakeRecord.subject_type == "document",
            RC15IntakeRecord.subject_id == document_id,
        )
    )
    if record:
        record.retry_count += 1
        record.last_retry_at = utcnow()
        record.updated_at = utcnow()


CASE_TRANSITIONS: dict[str, set[str]] = {
    "open": {"needs_review", "confirmed", "dismissed"},
    "needs_review": {"confirmed", "dismissed"},
    "confirmed": {"resolved", "needs_review", "dismissed"},
    "dismissed": {"needs_review"},
    "resolved": {"needs_review"},
    "superseded": set(),
}


def transition_case(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    case_id: str,
    action: str,
    note: str,
) -> DiscrepancyCase:
    item = db.scalar(
        select(DiscrepancyCase).where(DiscrepancyCase.id == case_id, DiscrepancyCase.tenant_id == tenant_id)
    )
    if item is None:
        raise LookupError("Segnalazione non trovata")
    normalized_note = note.strip()
    if len(normalized_note) < 3:
        raise ValueError("Una motivazione di almeno 3 caratteri è obbligatoria")
    target = "needs_review" if action == "reopen" else action
    if target not in {"needs_review", "confirmed", "dismissed", "resolved"}:
        raise ValueError("Transizione non valida")
    previous = item.status
    if target == previous:
        raise ValueError("La segnalazione è già nello stato richiesto")
    if target not in CASE_TRANSITIONS.get(previous, set()):
        raise ValueError(f"Transizione non consentita: {previous} → {target}")

    reviewer_ref, reviewer_user_id = resolve_reviewer_identity(
        db,
        tenant_id=tenant_id,
        actor_id=user_id,
    )
    item.status = target
    decision = ReviewDecision(
        tenant_id=tenant_id,
        case_id=item.id,
        user_id=reviewer_user_id,
        decision=target,
        note=normalized_note,
    )
    db.add(decision)
    db.flush()
    record_judgment_provenance(
        db,
        tenant_id=tenant_id,
        case_id=item.id,
        review_decision=decision,
        reviewer_ref=reviewer_ref,
        reviewer_user_id=reviewer_user_id,
        previous_state=previous,
    )
    add_audit(
        db,
        tenant_id,
        "case.reopened" if action == "reopen" else "case.transitioned",
        user_id,
        "discrepancy_case",
        item.id,
        {"from": previous, "to": target, "reason": normalized_note},
    )
    db.flush()
    return item


def economic_assessment_payload(item: RC15CaseEconomicAssessment | None) -> dict[str, Any]:
    if item is None:
        return {
            "state": "unknown",
            "potential_exposure": None,
            "confirmed_loss": None,
            "currency": None,
            "note": None,
            "assessed": False,
            "updated_at": None,
        }
    return {
        "state": item.state,
        "potential_exposure": _money(item.potential_exposure),
        "confirmed_loss": _money(item.confirmed_loss),
        "currency": item.currency,
        "note": item.note,
        "assessed": True,
        "updated_at": item.updated_at.isoformat(),
    }


def set_economic_assessment(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    case_id: str,
    *,
    state: str | None,
    potential_exposure: Decimal | None,
    confirmed_loss: Decimal | None,
    currency: str,
    note: str,
) -> RC15CaseEconomicAssessment:
    case_item = db.scalar(
        select(DiscrepancyCase.id).where(DiscrepancyCase.id == case_id, DiscrepancyCase.tenant_id == tenant_id)
    )
    if not case_item:
        raise LookupError("Segnalazione non trovata")
    if potential_exposure is not None and potential_exposure < 0:
        raise ValueError("L'importo potenziale non può essere negativo")
    if confirmed_loss is not None and confirmed_loss < 0:
        raise ValueError("La perdita confermata non può essere negativa")
    normalized_state = state
    if normalized_state is None:
        if confirmed_loss is not None:
            normalized_state = "confirmed_zero" if confirmed_loss == 0 else "loss_confirmed"
        elif potential_exposure is not None:
            normalized_state = "estimated"
        else:
            normalized_state = "unknown"
    allowed_states = {"unknown", "estimated", "confirmed_zero", "loss_confirmed", "not_applicable"}
    if normalized_state not in allowed_states:
        raise ValueError("Stato economico non valido")
    if normalized_state in {"unknown", "not_applicable"} and (
        potential_exposure is not None or confirmed_loss is not None
    ):
        raise ValueError("Uno stato sconosciuto/non applicabile non può contenere importi")
    if normalized_state == "estimated" and (potential_exposure is None or confirmed_loss is not None):
        raise ValueError("Lo stato stimato richiede importo potenziale e nessuna perdita confermata")
    if normalized_state == "confirmed_zero" and confirmed_loss != 0:
        raise ValueError("Lo stato confirmed_zero richiede perdita confermata pari a zero")
    if normalized_state == "loss_confirmed" and (confirmed_loss is None or confirmed_loss <= 0):
        raise ValueError("Lo stato loss_confirmed richiede una perdita confermata positiva")
    normalized_note = note.strip()
    if len(normalized_note) < 3:
        raise ValueError("La motivazione dell'impatto economico è obbligatoria")
    normalized_currency = currency.strip().upper()
    if not (3 <= len(normalized_currency) <= 8):
        raise ValueError("Valuta non valida")
    item = db.scalar(
        select(RC15CaseEconomicAssessment).where(
            RC15CaseEconomicAssessment.tenant_id == tenant_id,
            RC15CaseEconomicAssessment.case_id == case_id,
        )
    )
    if item is None:
        item = RC15CaseEconomicAssessment(
            tenant_id=tenant_id,
            case_id=case_id,
            state=normalized_state,
            potential_exposure=potential_exposure,
            confirmed_loss=confirmed_loss,
            currency=normalized_currency,
            note=normalized_note,
            assessed_by=user_id,
        )
        db.add(item)
    else:
        item.state = normalized_state
        item.potential_exposure = potential_exposure
        item.confirmed_loss = confirmed_loss
        item.currency = normalized_currency
        item.note = normalized_note
        item.assessed_by = user_id
        item.updated_at = utcnow()
    add_audit(
        db,
        tenant_id,
        "rc15.case_economic_assessed",
        user_id,
        "discrepancy_case",
        case_id,
        {
            "state": normalized_state,
            "potential_exposure": str(potential_exposure) if potential_exposure is not None else None,
            "confirmed_loss": str(confirmed_loss) if confirmed_loss is not None else None,
            "currency": normalized_currency,
        },
    )
    db.flush()
    return item


def case_rc15_payload(db: Session, tenant_id: str, case_id: str) -> dict[str, Any]:
    item = db.scalar(
        select(DiscrepancyCase)
        .options(selectinload(DiscrepancyCase.evidence))
        .where(DiscrepancyCase.id == case_id, DiscrepancyCase.tenant_id == tenant_id)
    )
    if item is None:
        raise LookupError("Segnalazione non trovata")
    assessment = db.scalar(
        select(RC15CaseEconomicAssessment).where(
            RC15CaseEconomicAssessment.tenant_id == tenant_id,
            RC15CaseEconomicAssessment.case_id == case_id,
        )
    )
    history = list(
        db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.tenant_id == tenant_id, ReviewDecision.case_id == case_id)
            .order_by(ReviewDecision.created_at.asc())
        )
    )
    return {
        "id": item.id,
        "chain_id": item.chain_id,
        "case_type": item.case_type,
        "severity": item.severity,
        "confidence": float(item.confidence or 0),
        "status": item.status,
        "title": item.title,
        "explanation": item.explanation,
        "recommended_action": item.recommended_action,
        "legacy_amount_estimate": _money(item.amount_estimate),
        "economic": economic_assessment_payload(assessment),
        "allowed_actions": sorted(
            ({"reopen"} if item.status in {"dismissed", "resolved"} else set())
            | ({target for target in CASE_TRANSITIONS.get(item.status, set()) if target != "needs_review"})
            | (
                {"needs_review"}
                if "needs_review" in CASE_TRANSITIONS.get(item.status, set())
                and item.status not in {"dismissed", "resolved"}
                else set()
            )
        ),
        "evidence": [
            {
                "id": evidence.id,
                "document_id": evidence.document_id,
                "document_line_id": evidence.document_line_id,
                "field_name": evidence.field_name,
                "observed_value": evidence.observed_value,
                "expected_value": evidence.expected_value,
                "note": evidence.note,
            }
            for evidence in item.evidence
        ],
        "history": [
            {
                "id": decision.id,
                "decision": decision.decision,
                "note": decision.note,
                "user_id": decision.user_id,
                "created_at": decision.created_at.isoformat(),
            }
            for decision in history
        ],
    }


def normalize_company_profile(config: dict[str, Any]) -> dict[str, Any]:
    merged = {**DEFAULT_COMPANY_PROFILE, **config}
    merged["default_currency"] = str(merged.get("default_currency") or "EUR").strip().upper()
    merged["rounding_decimals"] = int(merged.get("rounding_decimals", 2))
    merged["price_tolerance_percent"] = float(merged.get("price_tolerance_percent", 1.0))
    merged["quantity_tolerance_percent"] = float(merged.get("quantity_tolerance_percent", 0.0))
    if not (0 <= merged["rounding_decimals"] <= 6):
        raise ValueError("rounding_decimals deve essere tra 0 e 6")
    if not (0 <= merged["price_tolerance_percent"] <= 100):
        raise ValueError("price_tolerance_percent deve essere tra 0 e 100")
    if not (0 <= merged["quantity_tolerance_percent"] <= 100):
        raise ValueError("quantity_tolerance_percent deve essere tra 0 e 100")
    aliases = merged.get("unit_aliases") or {}
    if not isinstance(aliases, dict) or len(aliases) > 200:
        raise ValueError("unit_aliases non valido")
    merged["unit_aliases"] = {
        str(key).strip().casefold()[:40]: str(value).strip().upper()[:40]
        for key, value in aliases.items()
        if str(key).strip() and str(value).strip()
    }
    terms = merged.get("significant_terms") or []
    if not isinstance(terms, list) or len(terms) > 200:
        raise ValueError("significant_terms non valido")
    merged["significant_terms"] = sorted({str(item).strip().casefold()[:120] for item in terms if str(item).strip()})
    return merged


def company_profile_payload(item: RC15CompanyProfileVersion | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "id": item.id,
        "version": item.version,
        "label": item.label,
        "config": _json(item.config_json, {}),
        "config_hash": item.config_hash,
        "active": item.active,
        "created_at": item.created_at.isoformat(),
    }


def get_active_company_profile(db: Session, tenant_id: str) -> RC15CompanyProfileVersion | None:
    return db.scalar(
        select(RC15CompanyProfileVersion)
        .where(RC15CompanyProfileVersion.tenant_id == tenant_id, RC15CompanyProfileVersion.active.is_(True))
        .order_by(RC15CompanyProfileVersion.version.desc())
    )


def create_company_profile_version(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    label: str,
    config: dict[str, Any],
) -> tuple[RC15CompanyProfileVersion, bool]:
    normalized = normalize_company_profile(config)
    config_hash = _sha(normalized)
    existing = db.scalar(
        select(RC15CompanyProfileVersion).where(
            RC15CompanyProfileVersion.tenant_id == tenant_id,
            RC15CompanyProfileVersion.config_hash == config_hash,
        )
    )
    if existing is not None:
        for current in db.scalars(
            select(RC15CompanyProfileVersion).where(RC15CompanyProfileVersion.tenant_id == tenant_id)
        ):
            current.active = current.id == existing.id
        db.flush()
        return existing, False
    max_version = int(
        db.scalar(
            select(func.coalesce(func.max(RC15CompanyProfileVersion.version), 0)).where(
                RC15CompanyProfileVersion.tenant_id == tenant_id
            )
        )
        or 0
    )
    for current in db.scalars(
        select(RC15CompanyProfileVersion).where(
            RC15CompanyProfileVersion.tenant_id == tenant_id,
            RC15CompanyProfileVersion.active.is_(True),
        )
    ):
        current.active = False
    item = RC15CompanyProfileVersion(
        tenant_id=tenant_id,
        version=max_version + 1,
        label=label.strip() or f"Profilo v{max_version + 1}",
        config_json=_canonical_json(normalized),
        config_hash=config_hash,
        active=True,
        created_by=user_id,
    )
    db.add(item)
    db.flush()
    add_audit(
        db,
        tenant_id,
        "rc15.company_profile_version_created",
        user_id,
        "rc15_company_profile",
        item.id,
        {"version": item.version, "config_hash": config_hash},
    )
    return item, True


def ensure_company_profile(db: Session, tenant_id: str, user_id: str | None) -> RC15CompanyProfileVersion:
    active = get_active_company_profile(db, tenant_id)
    if active is not None:
        return active
    active, _ = create_company_profile_version(
        db, tenant_id, user_id, "Profilo aziendale iniziale", DEFAULT_COMPANY_PROFILE
    )
    return active


def _description_tokens(description: str | None, significant_terms: list[str]) -> set[str]:
    text = description or ""
    found = {match.group(0).strip().casefold().replace(",", ".") for match in _TOKEN_RE.finditer(text)}
    lowered = text.casefold()
    found.update(term for term in significant_terms if term and term in lowered)
    return found


def _line_group_key(line: DocumentLine) -> str:
    if line.sku and line.sku.strip():
        return f"sku:{line.sku.strip().casefold()}"
    description = (line.description or "").casefold()
    description = _TOKEN_RE.sub(" ", description)
    description = re.sub(r"\W+", " ", description).strip()
    return f"desc:{description[:180]}" if description else f"line:{line.id}"


def structured_text_differences(
    db: Session,
    tenant_id: str,
    chain_id: str,
    profile: RC15CompanyProfileVersion | None,
) -> list[dict[str, Any]]:
    config = _json(profile.config_json, {}) if profile else DEFAULT_COMPANY_PROFILE
    significant_terms = list(config.get("significant_terms") or [])
    links = list(
        db.scalars(
            select(ChainDocument).where(
                ChainDocument.tenant_id == tenant_id,
                ChainDocument.chain_id == chain_id,
            )
        )
    )
    if not links:
        return []
    role_by_document = {item.document_id: item.role for item in links}
    lines = list(
        db.scalars(
            select(DocumentLine).where(
                DocumentLine.tenant_id == tenant_id,
                DocumentLine.document_id.in_(list(role_by_document)),
            )
        )
    )
    grouped: dict[str, list[DocumentLine]] = defaultdict(list)
    for line in lines:
        grouped[_line_group_key(line)].append(line)
    differences: list[dict[str, Any]] = []
    for key, group in grouped.items():
        roles = {role_by_document.get(line.document_id) for line in group}
        if len(roles) < 2:
            continue
        ordered = sorted(group, key=lambda line: ROLE_ORDER.get(role_by_document.get(line.document_id, ""), 99))
        for field in ("color", "size", "lot", "unit_of_measure"):
            values = {
                str(getattr(line, field)).strip().casefold()
                for line in ordered
                if getattr(line, field) is not None and str(getattr(line, field)).strip()
            }
            if len(values) > 1:
                differences.append(
                    {
                        "group": key,
                        "kind": "attribute",
                        "field": field,
                        "values": [
                            {
                                "role": role_by_document.get(line.document_id),
                                "document_id": line.document_id,
                                "line_id": line.id,
                                "value": getattr(line, field),
                            }
                            for line in ordered
                            if getattr(line, field) is not None
                        ],
                    }
                )
        token_sets = [(_description_tokens(line.description, significant_terms), line) for line in ordered]
        distinct = {tuple(sorted(tokens)) for tokens, _line in token_sets if tokens}
        if len(distinct) > 1:
            differences.append(
                {
                    "group": key,
                    "kind": "commercial_text",
                    "field": "description_tokens",
                    "values": [
                        {
                            "role": role_by_document.get(line.document_id),
                            "document_id": line.document_id,
                            "line_id": line.id,
                            "description": line.description,
                            "tokens": sorted(tokens),
                        }
                        for tokens, line in token_sets
                    ],
                }
            )
    return differences[:200]


def ensure_practice_for_chain(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    chain_id: str,
    retention_end: date | None = None,
) -> tuple[RC15Practice, bool]:
    chain = db.scalar(
        select(OperationChain).where(OperationChain.id == chain_id, OperationChain.tenant_id == tenant_id)
    )
    if chain is None:
        raise LookupError("Catena documentale non trovata")
    existing = db.scalar(
        select(RC15Practice).where(RC15Practice.tenant_id == tenant_id, RC15Practice.chain_id == chain_id)
    )
    if existing is not None:
        if retention_end is not None:
            existing.retention_end = retention_end
        return existing, False
    profile = ensure_company_profile(db, tenant_id, user_id)
    item = RC15Practice(
        tenant_id=tenant_id,
        chain_id=chain.id,
        profile_version_id=profile.id,
        retention_end=retention_end,
        created_by=user_id,
    )
    db.add(item)
    db.flush()
    add_audit(
        db,
        tenant_id,
        "rc15.practice_created",
        user_id,
        "rc15_practice",
        item.id,
        {"chain_id": chain.id, "profile_version": profile.version},
    )
    return item, True


def _practice_documents(db: Session, tenant_id: str, chain_id: str) -> list[tuple[ChainDocument, Document]]:
    links = list(
        db.scalars(
            select(ChainDocument)
            .where(ChainDocument.tenant_id == tenant_id, ChainDocument.chain_id == chain_id)
            .order_by(ChainDocument.role, ChainDocument.sequence_no)
        )
    )
    if not links:
        return []
    docs = {
        item.id: item
        for item in db.scalars(
            select(Document)
            .options(selectinload(Document.lines))
            .where(Document.tenant_id == tenant_id, Document.id.in_([link.document_id for link in links]))
        )
    }
    return [(link, docs[link.document_id]) for link in links if link.document_id in docs]


def practice_payload(db: Session, tenant_id: str, item: RC15Practice) -> dict[str, Any]:
    if item.status == "deleted" or not item.chain_id:
        return {
            "id": item.id,
            "status": item.status,
            "chain_id": None,
            "reference_key": None,
            "retention_end": item.retention_end.isoformat() if item.retention_end else None,
            "retention_expired": bool(item.retention_end and item.retention_end < date.today()),
            "tombstone_hash": item.tombstone_hash,
            "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
            "profile": None,
            "documents": [],
            "cases": [],
            "text_differences": [],
        }
    chain = db.scalar(
        select(OperationChain).where(OperationChain.id == item.chain_id, OperationChain.tenant_id == tenant_id)
    )
    if chain is None:
        raise LookupError("Catena della pratica non trovata")
    profile = (
        db.scalar(
            select(RC15CompanyProfileVersion).where(
                RC15CompanyProfileVersion.id == item.profile_version_id,
                RC15CompanyProfileVersion.tenant_id == tenant_id,
            )
        )
        if item.profile_version_id
        else None
    )
    linked = _practice_documents(db, tenant_id, chain.id)
    cases = list(
        db.scalars(
            select(DiscrepancyCase)
            .where(DiscrepancyCase.tenant_id == tenant_id, DiscrepancyCase.chain_id == chain.id)
            .order_by(DiscrepancyCase.created_at.desc())
        )
    )
    assessments = {
        assessment.case_id: assessment
        for assessment in db.scalars(
            select(RC15CaseEconomicAssessment).where(
                RC15CaseEconomicAssessment.tenant_id == tenant_id,
                RC15CaseEconomicAssessment.case_id.in_([case.id for case in cases] or [""]),
            )
        )
    }
    return {
        "id": item.id,
        "status": item.status,
        "chain_id": chain.id,
        "reference_key": chain.reference_key,
        "chain_status": chain.status,
        "chain_confidence": float(chain.confidence or 0),
        "retention_end": item.retention_end.isoformat() if item.retention_end else None,
        "retention_expired": bool(item.retention_end and item.retention_end < date.today()),
        "tombstone_hash": item.tombstone_hash,
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
        "profile": company_profile_payload(profile),
        "documents": [
            {
                "role": link.role,
                "sequence_no": link.sequence_no,
                "id": document.id,
                "number": document.number,
                "filename": document.source_filename,
                "document_type": document.document_type,
                "parse_status": document.parse_status,
                "confidence": float(document.confidence or 0),
                "file_hash": document.file_hash,
                "file_available": Path(document.storage_path).is_file(),
                "line_count": len(document.lines),
            }
            for link, document in linked
        ],
        "cases": [
            {
                "id": case.id,
                "case_type": case.case_type,
                "severity": case.severity,
                "status": case.status,
                "confidence": float(case.confidence or 0),
                "title": case.title,
                "economic": economic_assessment_payload(assessments.get(case.id)),
            }
            for case in cases
        ],
        "text_differences": structured_text_differences(db, tenant_id, chain.id, profile),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def list_practices(db: Session, tenant_id: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    stmt = select(RC15Practice).where(RC15Practice.tenant_id == tenant_id)
    if not include_deleted:
        stmt = stmt.where(RC15Practice.status != "deleted")
    items = list(db.scalars(stmt.order_by(RC15Practice.updated_at.desc())))
    return [practice_payload(db, tenant_id, item) for item in items]


def set_practice_status(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    practice_id: str,
    status: str,
) -> RC15Practice:
    if status not in {"active", "archived"}:
        raise ValueError("Stato pratica non valido")
    item = db.scalar(select(RC15Practice).where(RC15Practice.id == practice_id, RC15Practice.tenant_id == tenant_id))
    if item is None or item.status == "deleted":
        raise LookupError("Pratica non trovata")
    previous = item.status
    item.status = status
    add_audit(
        db,
        tenant_id,
        "rc15.practice_archived" if status == "archived" else "rc15.practice_restored",
        user_id,
        "rc15_practice",
        item.id,
        {"from": previous, "to": status},
    )
    db.flush()
    return item


def build_practice_export(
    db: Session,
    tenant_id: str,
    practice_id: str,
    *,
    include_originals: bool = False,
) -> tuple[bytes, str]:
    item = db.scalar(select(RC15Practice).where(RC15Practice.id == practice_id, RC15Practice.tenant_id == tenant_id))
    if item is None or item.status == "deleted" or not item.chain_id:
        raise LookupError("Pratica non trovata")
    payload = practice_payload(db, tenant_id, item)
    linked = _practice_documents(db, tenant_id, item.chain_id)
    case_ids = [case["id"] for case in payload["cases"]]
    evidence: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    if case_ids:
        for case_id in case_ids:
            case_item = db.scalar(
                select(DiscrepancyCase)
                .options(selectinload(DiscrepancyCase.evidence))
                .where(DiscrepancyCase.id == case_id, DiscrepancyCase.tenant_id == tenant_id)
            )
            if case_item:
                evidence.extend(
                    {
                        "case_id": case_item.id,
                        "document_id": ev.document_id,
                        "document_line_id": ev.document_line_id,
                        "field_name": ev.field_name,
                        "observed_value": ev.observed_value,
                        "expected_value": ev.expected_value,
                        "note": ev.note,
                    }
                    for ev in case_item.evidence
                )
        decisions = [
            {
                "case_id": decision.case_id,
                "decision": decision.decision,
                "note": decision.note,
                "created_at": decision.created_at.isoformat(),
            }
            for decision in db.scalars(
                select(ReviewDecision)
                .where(ReviewDecision.tenant_id == tenant_id, ReviewDecision.case_id.in_(case_ids))
                .order_by(ReviewDecision.created_at)
            )
        ]
    export_payload = {
        "schema": "thistinti.rc15.practice-export.v1",
        "product_version": RELEASE_VERSION,
        "generated_at": utcnow().isoformat(),
        "practice": payload,
        "evidence": evidence,
        "review_decisions": decisions,
        "originals_included": include_originals,
    }
    data_bytes = (json.dumps(export_payload, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8")
    manifest = {
        "schema": "thistinti.rc15.practice-export-manifest.v1",
        "practice_id": item.id,
        "product_version": RELEASE_VERSION,
        "files": {"practice.json": hashlib.sha256(data_bytes).hexdigest()},
        "source_document_hashes": sorted(document.file_hash for _link, document in linked),
        "originals_included": include_originals,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("practice.json", data_bytes)
        if include_originals:
            for index, (_link, document) in enumerate(linked, start=1):
                path = Path(document.storage_path)
                if path.is_file() and _within_storage(path):
                    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", document.source_filename).strip("._") or "document"
                    archive_name = f"originals/{index:03d}-{safe[:160]}"
                    raw = path.read_bytes()
                    archive.writestr(archive_name, raw)
                    manifest["files"][archive_name] = hashlib.sha256(raw).hexdigest()
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        archive.writestr("manifest.json", manifest_bytes)
    return buffer.getvalue(), _sha(manifest)


def delete_practice_transaction(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    practice_id: str,
) -> dict[str, Any]:
    item = db.scalar(select(RC15Practice).where(RC15Practice.id == practice_id, RC15Practice.tenant_id == tenant_id))
    if item is None or item.status == "deleted" or not item.chain_id:
        raise LookupError("Pratica non trovata")
    active_pilot = db.scalar(
        select(RC15PilotWorkspace.id)
        .join(RC15PilotCase, RC15PilotCase.pilot_id == RC15PilotWorkspace.id)
        .where(
            RC15PilotWorkspace.tenant_id == tenant_id,
            RC15PilotCase.practice_id == item.id,
            RC15PilotWorkspace.status != "archived",
        )
        .limit(1)
    )
    if active_pilot:
        raise ValueError("La pratica appartiene a un pilot non archiviato")
    chain = db.scalar(
        select(OperationChain).where(OperationChain.id == item.chain_id, OperationChain.tenant_id == tenant_id)
    )
    if chain is None:
        raise LookupError("Catena della pratica non trovata")
    linked = _practice_documents(db, tenant_id, chain.id)
    tombstone = {
        "schema": "thistinti.rc15.practice-tombstone.v1",
        "practice_id": item.id,
        "deleted_at": utcnow().isoformat(),
        "product_version": RELEASE_VERSION,
        "document_hashes": sorted(document.file_hash for _link, document in linked),
    }
    tombstone_hash = _sha(tombstone)
    staging_dir = settings.storage_dir / ".rc15-delete" / item.id
    staging_dir.mkdir(parents=True, exist_ok=True)
    moved: list[tuple[Path, Path]] = []
    try:
        for index, (_link, document) in enumerate(linked, start=1):
            original = Path(document.storage_path)
            if not original.is_file():
                continue
            if not _within_storage(original):
                raise ValueError("Percorso documento non sicuro: cancellazione bloccata")
            staged = staging_dir / f"{index:03d}-{document.file_hash}"
            os.replace(original, staged)
            moved.append((original, staged))
        document_ids = [document.id for _link, document in linked]
        for document in [document for _link, document in linked]:
            db.delete(document)
        db.delete(chain)
        item.chain_id = None
        item.status = "deleted"
        item.tombstone_hash = tombstone_hash
        item.deleted_at = utcnow()
        add_audit(
            db,
            tenant_id,
            "rc15.practice_deleted",
            user_id,
            "rc15_practice",
            item.id,
            {"tombstone_hash": tombstone_hash, "document_count": len(document_ids)},
        )
        db.commit()
    except Exception:
        db.rollback()
        for original, staged in reversed(moved):
            if staged.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, original)
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    physical_cleanup_pending = False
    for _original, staged in moved:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            physical_cleanup_pending = True
    try:
        staging_dir.rmdir()
    except OSError:
        if staging_dir.exists():
            physical_cleanup_pending = True
    return {
        "ok": True,
        "practice_id": item.id,
        "tombstone_hash": tombstone_hash,
        "document_count": len(linked),
        "physical_cleanup_pending": physical_cleanup_pending,
    }
