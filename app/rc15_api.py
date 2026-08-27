from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .audit import add_audit
from .db import get_db
from .models import Document, Supplier, utcnow
from .parsers import ParseError
from .rc15_models import (
    RC15CompanyProfileVersion,
    RC15IntakeRecord,
    RC15PilotWorkspace,
    RC15Practice,
)
from .security import AuthContext, current_user, require_admin, require_ingest, require_reviewer
from .services.ingestion import reprocess_document
from .services.rc15 import (
    _automatic_document_intake,
    build_practice_export,
    case_rc15_payload,
    classify_intake,
    company_profile_payload,
    create_company_profile_version,
    delete_practice_transaction,
    economic_assessment_payload,
    ensure_company_profile,
    ensure_practice_for_chain,
    get_active_company_profile,
    list_intake,
    list_practices,
    normalize_company_profile,
    practice_payload,
    record_document_retry,
    set_economic_assessment,
    set_practice_status,
    transition_case,
)
from .services.rc15_pilot import (
    add_pilot_practice,
    create_pilot,
    freeze_pilot,
    pilot_payload,
    render_pilot_markdown,
    run_pilot,
    update_pilot_case,
)
from .version import RELEASE_VERSION


router = APIRouter(prefix="/api/rc15", tags=["RC15 Pilot-Ready"])


class IntakeClassificationRequest(BaseModel):
    state: Literal["acquired", "review_required", "not_acquired", "blocked", "out_of_scope"]
    category: Literal["ok", "degraded", "hostile", "out_of_scope", "parser_limit", "operator_input", "security_block"]
    phase: str | None = Field(default=None, max_length=80)
    reason: str = Field(min_length=3, max_length=3000)
    note: str | None = Field(default=None, max_length=3000)


class DocumentRetryRequest(BaseModel):
    document_type: (
        Literal["proposal", "order", "confirmation", "delivery", "invoice", "payment", "return", "credit_note"] | None
    ) = None
    supplier_name: str | None = Field(default=None, max_length=240)
    number: str | None = Field(default=None, max_length=120)
    document_date: date | None = None


class CaseTransitionRequest(BaseModel):
    action: Literal["needs_review", "confirmed", "dismissed", "resolved", "reopen"]
    note: str = Field(min_length=3, max_length=2000)


class EconomicAssessmentRequest(BaseModel):
    state: Literal["unknown", "estimated", "confirmed_zero", "loss_confirmed", "not_applicable"] | None = None
    potential_exposure: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    confirmed_loss: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=8)
    note: str = Field(min_length=3, max_length=2000)


class CompanyProfileConfig(BaseModel):
    default_currency: str = Field(default="EUR", min_length=3, max_length=8)
    rounding_decimals: int = Field(default=2, ge=0, le=6)
    price_tolerance_percent: float = Field(default=1.0, ge=0, le=100)
    quantity_tolerance_percent: float = Field(default=0.0, ge=0, le=100)
    unit_aliases: dict[str, str] = Field(default_factory=dict)
    significant_terms: list[str] = Field(default_factory=list, max_length=200)


class CompanyProfileCreateRequest(BaseModel):
    label: str = Field(min_length=2, max_length=180)
    config: CompanyProfileConfig


class PracticeCreateRequest(BaseModel):
    retention_end: date | None = None


class PracticeDeleteRequest(BaseModel):
    confirm_practice_id: str


class PilotCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    authorization_reference: str = Field(min_length=3, max_length=240)
    reviewer_primary: str = Field(min_length=2, max_length=120)
    reviewer_secondary: str = Field(min_length=2, max_length=120)
    scope: str = Field(min_length=10, max_length=3000)
    retention_end: date | None = None

    @model_validator(mode="after")
    def reviewers_must_differ(self):
        if self.reviewer_primary.strip().casefold() == self.reviewer_secondary.strip().casefold():
            raise ValueError("Servono due revisori distinti")
        return self


class GroundTruthFinding(BaseModel):
    case_type: str = Field(min_length=2, max_length=80)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    potential_exposure: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)


class GroundTruthPayload(BaseModel):
    findings: list[GroundTruthFinding] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=3000)


class PilotPracticeRequest(BaseModel):
    practice_id: str


class PilotCaseUpdateRequest(BaseModel):
    reviewer_primary: GroundTruthPayload | None = None
    reviewer_secondary: GroundTruthPayload | None = None
    adjudicated: GroundTruthPayload | None = None
    manual_seconds: float | None = Field(default=None, gt=0)
    assisted_seconds: float | None = Field(default=None, gt=0)
    user_score: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=3000)


@router.get("/status")
def rc15_status(ctx: AuthContext = Depends(current_user)) -> dict[str, Any]:
    return {
        "release": "RC15 Pilot-Ready",
        "product_version": RELEASE_VERSION,
        "tenant_id": ctx.tenant_id,
        "capabilities": [
            "intake_center",
            "audited_case_lifecycle",
            "economic_assessment",
            "company_profile_versions",
            "practice_export_archive_delete",
            "integrated_pilot",
            "structured_attribute_differences",
        ],
    }


@router.get("/intake")
def intake_center(
    include_success: bool = Query(default=True),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return list_intake(db, ctx.tenant_id, include_success=include_success)


@router.post("/intake/{subject_type}/{subject_id}/classify")
def classify_intake_subject(
    subject_type: Literal["document", "job"],
    subject_id: str,
    payload: IntakeClassificationRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = classify_intake(
            db,
            ctx.tenant_id,
            ctx.user_id,
            subject_type=subject_type,
            subject_id=subject_id,
            state=payload.state,
            category=payload.category,
            phase=payload.phase,
            reason=payload.reason,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {
        "ok": True,
        "classification": {
            "state": item.state,
            "category": item.category,
            "phase": item.phase,
            "reason": item.reason,
            "note": item.note,
            "automatic": item.automatic,
            "updated_at": item.updated_at.isoformat(),
        },
    }


@router.post("/intake/documents/{document_id}/retry")
def retry_intake_document(
    document_id: str,
    payload: DocumentRetryRequest,
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.lines))
        .where(Document.id == document_id, Document.tenant_id == ctx.tenant_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    record_document_retry(db, ctx.tenant_id, document.id)
    try:
        document = reprocess_document(
            db,
            document,
            {
                "document_type": payload.document_type,
                "supplier_name": payload.supplier_name,
                "number": payload.number,
                "document_date": payload.document_date.isoformat() if payload.document_date else None,
            },
        )
    except ParseError as exc:
        record = db.scalar(
            select(RC15IntakeRecord).where(
                RC15IntakeRecord.tenant_id == ctx.tenant_id,
                RC15IntakeRecord.subject_type == "document",
                RC15IntakeRecord.subject_id == document.id,
            )
        )
        if record is None:
            auto = _automatic_document_intake(document)
            record = RC15IntakeRecord(
                tenant_id=ctx.tenant_id,
                subject_type="document",
                subject_id=document.id,
                state="not_acquired",
                category="parser_limit",
                phase="reprocess",
                reason=str(exc),
                automatic=True,
                retry_count=1,
                last_retry_at=utcnow(),
            )
            db.add(record)
        else:
            record.state = "not_acquired"
            record.category = "parser_limit"
            record.phase = "reprocess"
            record.reason = str(exc)
            record.automatic = True
            record.last_retry_at = utcnow()
        add_audit(
            db,
            ctx.tenant_id,
            "rc15.intake_retry_failed",
            ctx.user_id,
            "document",
            document.id,
            {"reason": str(exc)},
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    auto = _automatic_document_intake(document)
    record = db.scalar(
        select(RC15IntakeRecord).where(
            RC15IntakeRecord.tenant_id == ctx.tenant_id,
            RC15IntakeRecord.subject_type == "document",
            RC15IntakeRecord.subject_id == document.id,
        )
    )
    if record:
        record.state = auto["state"]
        record.category = auto["category"]
        record.phase = auto.get("phase")
        record.reason = auto["reason"]
        record.automatic = True
        record.last_retry_at = utcnow()
    add_audit(db, ctx.tenant_id, "rc15.intake_retried", ctx.user_id, "document", document.id)
    db.commit()
    supplier = db.get(Supplier, document.supplier_id) if document.supplier_id else None
    return {
        "ok": True,
        "document": {
            "id": document.id,
            "filename": document.source_filename,
            "document_type": document.document_type,
            "supplier": supplier.legal_name if supplier else None,
            "parse_status": document.parse_status,
            "confidence": float(document.confidence or 0),
            "classification": auto,
        },
    }


@router.get("/cases/{case_id}")
def rc15_case_detail(
    case_id: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return case_rc15_payload(db, ctx.tenant_id, case_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/cases/{case_id}/transition")
def rc15_case_transition(
    case_id: str,
    payload: CaseTransitionRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = transition_case(db, ctx.tenant_id, ctx.user_id, case_id, payload.action, payload.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "status": item.status, "case": case_rc15_payload(db, ctx.tenant_id, item.id)}


@router.put("/cases/{case_id}/economic")
def rc15_case_economic(
    case_id: str,
    payload: EconomicAssessmentRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = set_economic_assessment(
            db,
            ctx.tenant_id,
            ctx.user_id,
            case_id,
            state=payload.state,
            potential_exposure=payload.potential_exposure,
            confirmed_loss=payload.confirmed_loss,
            currency=payload.currency,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "economic": economic_assessment_payload(item)}


@router.get("/company-profile")
def rc15_company_profile(
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = get_active_company_profile(db, ctx.tenant_id)
    if item is None and ctx.role in {"admin", "reviewer"}:
        item = ensure_company_profile(db, ctx.tenant_id, ctx.user_id)
        db.commit()
    return {"active": company_profile_payload(item)}


@router.get("/company-profile/versions")
def rc15_company_profile_versions(
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    items = list(
        db.scalars(
            select(RC15CompanyProfileVersion)
            .where(RC15CompanyProfileVersion.tenant_id == ctx.tenant_id)
            .order_by(RC15CompanyProfileVersion.version.desc())
        )
    )
    return [company_profile_payload(item) for item in items]


@router.post("/company-profile/versions", status_code=201)
def rc15_create_company_profile(
    payload: CompanyProfileCreateRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item, created = create_company_profile_version(
            db,
            ctx.tenant_id,
            ctx.user_id,
            payload.label,
            normalize_company_profile(payload.config.model_dump()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"created": created, "profile": company_profile_payload(item)}


@router.get("/practices")
def rc15_practices(
    include_deleted: bool = Query(default=False),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return list_practices(db, ctx.tenant_id, include_deleted=include_deleted)


@router.post("/practices/from-chain/{chain_id}", status_code=201)
def rc15_create_practice(
    chain_id: str,
    payload: PracticeCreateRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item, created = ensure_practice_for_chain(db, ctx.tenant_id, ctx.user_id, chain_id, payload.retention_end)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"created": created, "practice": practice_payload(db, ctx.tenant_id, item)}


@router.get("/practices/{practice_id}")
def rc15_practice_detail(
    practice_id: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.scalar(
        select(RC15Practice).where(RC15Practice.id == practice_id, RC15Practice.tenant_id == ctx.tenant_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pratica non trovata")
    try:
        return practice_payload(db, ctx.tenant_id, item)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/practices/{practice_id}/archive")
def rc15_archive_practice(
    practice_id: str,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = set_practice_status(db, ctx.tenant_id, ctx.user_id, practice_id, "archived")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "practice": practice_payload(db, ctx.tenant_id, item)}


@router.post("/practices/{practice_id}/restore")
def rc15_restore_practice(
    practice_id: str,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = set_practice_status(db, ctx.tenant_id, ctx.user_id, practice_id, "active")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "practice": practice_payload(db, ctx.tenant_id, item)}


@router.get(
    "/practices/{practice_id}/export",
    response_class=Response,
    responses={
        200: {
            "description": "Archivio ZIP verificabile della pratica",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def rc15_export_practice(
    practice_id: str,
    include_originals: bool = Query(default=False),
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> Response:
    try:
        content, manifest_hash = build_practice_export(
            db,
            ctx.tenant_id,
            practice_id,
            include_originals=include_originals,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    add_audit(
        db,
        ctx.tenant_id,
        "rc15.practice_exported",
        ctx.user_id,
        "rc15_practice",
        practice_id,
        {"manifest_hash": manifest_hash, "originals_included": include_originals},
    )
    db.commit()
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="thistinti-practice-{practice_id[:8]}.zip"',
            "X-ThisTinti-Manifest-SHA256": manifest_hash,
        },
    )


@router.delete("/practices/{practice_id}")
def rc15_delete_practice(
    practice_id: str,
    payload: PracticeDeleteRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.confirm_practice_id != practice_id:
        raise HTTPException(status_code=422, detail="Conferma pratica non corrispondente")
    try:
        return delete_practice_transaction(db, ctx.tenant_id, ctx.user_id, practice_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/pilots")
def rc15_pilots(
    include_archived: bool = Query(default=False),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(RC15PilotWorkspace).where(RC15PilotWorkspace.tenant_id == ctx.tenant_id)
    if not include_archived:
        stmt = stmt.where(RC15PilotWorkspace.status != "archived")
    items = list(db.scalars(stmt.order_by(RC15PilotWorkspace.updated_at.desc())))
    return [pilot_payload(db, ctx.tenant_id, item, include_ground_truth=False) for item in items]


@router.post("/pilots", status_code=201)
def rc15_create_pilot(
    payload: PilotCreateRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = create_pilot(
            db,
            ctx.tenant_id,
            ctx.user_id,
            name=payload.name,
            authorization_reference=payload.authorization_reference,
            reviewer_primary=payload.reviewer_primary,
            reviewer_secondary=payload.reviewer_secondary,
            scope=payload.scope,
            retention_end=payload.retention_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return pilot_payload(db, ctx.tenant_id, item, include_ground_truth=True)


@router.get("/pilots/{pilot_id}")
def rc15_pilot_detail(
    pilot_id: str,
    include_ground_truth: bool = Query(default=False),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.scalar(
        select(RC15PilotWorkspace).where(
            RC15PilotWorkspace.id == pilot_id, RC15PilotWorkspace.tenant_id == ctx.tenant_id
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pilot non trovato")
    if include_ground_truth and ctx.role != "admin":
        raise HTTPException(status_code=403, detail="Solo un amministratore può leggere la ground truth interna")
    return pilot_payload(db, ctx.tenant_id, item, include_ground_truth=include_ground_truth)


@router.post("/pilots/{pilot_id}/practices", status_code=201)
def rc15_add_pilot_practice(
    pilot_id: str,
    payload: PilotPracticeRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = add_pilot_practice(db, ctx.tenant_id, pilot_id, payload.practice_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    add_audit(
        db,
        ctx.tenant_id,
        "rc15.pilot_practice_added",
        ctx.user_id,
        "rc15_pilot_case",
        item.id,
        {"pilot_id": pilot_id, "practice_id": payload.practice_id},
    )
    db.commit()
    return {"ok": True, "case_id": item.id}


@router.patch("/pilots/{pilot_id}/cases/{pilot_case_id}")
def rc15_update_pilot_case(
    pilot_id: str,
    pilot_case_id: str,
    payload: PilotCaseUpdateRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = update_pilot_case(
            db,
            ctx.tenant_id,
            pilot_id,
            pilot_case_id,
            reviewer_primary=payload.reviewer_primary.model_dump(mode="json")
            if payload.reviewer_primary is not None
            else None,
            reviewer_secondary=payload.reviewer_secondary.model_dump(mode="json")
            if payload.reviewer_secondary is not None
            else None,
            adjudicated=payload.adjudicated.model_dump(mode="json") if payload.adjudicated is not None else None,
            manual_seconds=payload.manual_seconds,
            assisted_seconds=payload.assisted_seconds,
            user_score=payload.user_score,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    add_audit(
        db,
        ctx.tenant_id,
        "rc15.pilot_case_updated",
        ctx.user_id,
        "rc15_pilot_case",
        item.id,
        {
            "pilot_id": pilot_id,
            "ground_truth_changed": any(
                value is not None
                for value in (payload.reviewer_primary, payload.reviewer_secondary, payload.adjudicated)
            ),
            "measurement_changed": any(
                value is not None for value in (payload.manual_seconds, payload.assisted_seconds, payload.user_score)
            ),
        },
    )
    db.commit()
    return {"ok": True, "pilot": rc15_pilot_detail(pilot_id, False, ctx, db)}


@router.post("/pilots/{pilot_id}/freeze")
def rc15_freeze_pilot(
    pilot_id: str,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = freeze_pilot(db, ctx.tenant_id, ctx.user_id, pilot_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return pilot_payload(db, ctx.tenant_id, item, include_ground_truth=False)


@router.post("/pilots/{pilot_id}/run")
def rc15_run_pilot(
    pilot_id: str,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = run_pilot(db, ctx.tenant_id, ctx.user_id, pilot_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return pilot_payload(db, ctx.tenant_id, item, include_ground_truth=False)


@router.get(
    "/pilots/{pilot_id}/report",
    response_class=Response,
    responses={
        200: {
            "description": "Rapporto pilot redatto in JSON o Markdown",
            "content": {
                "application/json": {"schema": {"type": "object", "additionalProperties": True}},
                "text/markdown": {"schema": {"type": "string"}},
            },
        }
    },
)
def rc15_pilot_report(
    pilot_id: str,
    format: Literal["json", "markdown"] = Query(default="json"),
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> Response:
    item = db.scalar(
        select(RC15PilotWorkspace).where(
            RC15PilotWorkspace.id == pilot_id, RC15PilotWorkspace.tenant_id == ctx.tenant_id
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pilot non trovato")
    report = pilot_payload(db, ctx.tenant_id, item, include_ground_truth=False)
    if format == "markdown":
        content = render_pilot_markdown(item)
        media_type = "text/markdown; charset=utf-8"
        extension = "md"
    else:
        content = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        media_type = "application/json"
        extension = "json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="thistinti-pilot-{item.id[:8]}.{extension}"'},
    )


@router.post("/pilots/{pilot_id}/archive")
def rc15_archive_pilot(
    pilot_id: str,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.scalar(
        select(RC15PilotWorkspace).where(
            RC15PilotWorkspace.id == pilot_id, RC15PilotWorkspace.tenant_id == ctx.tenant_id
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pilot non trovato")
    item.status = "archived"
    add_audit(db, ctx.tenant_id, "rc15.pilot_archived", ctx.user_id, "rc15_pilot", item.id)
    db.commit()
    return {"ok": True}
