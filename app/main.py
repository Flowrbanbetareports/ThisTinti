from __future__ import annotations

import hmac
import json
import logging
import mimetypes
import os
import secrets
import shutil
import tempfile
import time
import uuid
import zipfile
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from .audit import add_audit, verify_audit_chain
from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .legal import LEGAL_NOTICE_VERSION
from .models import (
    ActivityProfile,
    ApiCredential,
    AuditEvent,
    AuthSession,
    ChainDocument,
    DiscrepancyCase,
    DiscoveryRun,
    Document,
    DocumentLine,
    ItemAlias,
    OperationChain,
    ProcessingJob,
    ReviewDecision,
    RuleProposal,
    Supplier,
    Tenant,
    User,
    ValidationDataset,
    ValidationRun,
    WorkerHeartbeat,
    utcnow,
)
from .schemas import (
    AdminPasswordResetRequest,
    AnonymousPatternPackResponse,
    ApiCredentialCreateRequest,
    AuthResponse,
    ActivityProfileDecisionRequest,
    ChainAttachRequest,
    DashboardResponse,
    DiscoveryRunRequest,
    LoginRequest,
    ItemAliasConfirmRequest,
    IntelligenceSimulationRequest,
    ChainIntelligenceResponse,
    RiskAssessmentResponse,
    RedTeamResponse,
    OkResponse,
    PasswordChangeRequest,
    ProcessingJobEnvelopeResponse,
    ReadinessResponse,
    RegisterRequest,
    ReprocessRequest,
    ReviewRequest,
    RuleDecisionRequest,
    UserCreateRequest,
    UserRoleRequest,
    UserStatusRequest,
    ValidationAutomationApprovalRequest,
    ValidationAutomationApprovalResponse,
    ValidationDatasetPayload,
    ValidationDatasetStatusRequest,
)
from .security import (
    AuthContext,
    create_session_token,
    current_user,
    hash_password,
    issue_api_credential_secret,
    require_admin,
    require_ingest,
    require_reviewer,
    revoke_session,
    verify_password,
)
from .services.file_security import probe_malware_scanner
from .services.ingestion import ingest_path, reprocess_document
from .services.jobs import enqueue_job, job_json
from .services.rules import analyze_chain
from .services.rate_limit import consume_rate_limit
from .services.validation import ENGINE_VERSION, run_validation_dataset
from .services.validation_reporting import build_validation_report, render_validation_report_markdown
from .services.line_matching import alias_tokens
from .services.comparison import build_chain_comparison
from .services.discovery import DiscoverySettings, maybe_run_discovery, run_discovery
from .services.intelligence import (
    assess_risk,
    build_anonymous_pattern_pack,
    build_intelligence_bundle,
    run_self_red_team,
)
from .parsers import ParseError
from .parsers.ocr import ocr_runtime_available
from .version import MIN_AUTOMATION_VALIDATION_SCENARIOS, RELEASE_VERSION

if settings.auto_create_schema:
    Base.metadata.create_all(bind=engine)

logging.basicConfig(
    level=os.getenv("THISTINTI_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("thistinti")
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)
_DUMMY_PASSWORD_HASH = hash_password("ThisTinti-dummy-password-never-used")


def _consume_request_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    if settings.database_rate_limiting:
        try:
            with SessionLocal() as rate_db:
                allowed, _count = consume_rate_limit(rate_db, key=key, limit=limit, window_seconds=window_seconds)
                rate_db.commit()
                return allowed
        except Exception:
            logger.exception("database_rate_limit_failed key=%s", key)
            if settings.environment == "production":
                raise
    now = time.monotonic()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def _active_admin_count(db: Session, tenant_id: str) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.role == "admin",
                User.active.is_(True),
            )
        )
        or 0
    )


def _auth_response(
    db: Session, user: User, tenant: Tenant, *, include_token: bool, status_code: int = 200
) -> JSONResponse:
    token = create_session_token(db, user, tenant)
    db.commit()
    organization = tenant.name
    csrf_token = secrets.token_urlsafe(32)
    content = {
        "user": {
            "id": user.id,
            "tenant_id": user.tenant_id,
            "email": user.email,
            "role": user.role,
            "organization": organization,
        }
    }
    if include_token:
        content["token"] = token
    response = JSONResponse(status_code=status_code, content=content)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.token_ttl_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=settings.token_ttl_seconds,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    return response


app = FastAPI(
    title="ThisTinti",
    version=RELEASE_VERSION,
    description="Document integrity and discrepancy review platform.",
)


def _reanalyze_tenant_chains(db: Session, tenant_id: str) -> int:
    chains = list(db.scalars(select(OperationChain).where(OperationChain.tenant_id == tenant_id)))
    for chain in chains:
        analyze_chain(db, chain)
    return len(chains)


def _ensure_synchronous_ingestion_allowed() -> None:
    if not settings.allow_synchronous_ingestion:
        raise HTTPException(
            status_code=409,
            detail="Synchronous ingestion is disabled; submit a persistent processing job instead",
        )


def _job_requester(ctx: AuthContext) -> dict[str, str | None]:
    return {
        "created_by": ctx.user_id if ctx.principal_type == "user_session" else None,
        "created_by_api_credential": ctx.user_id if ctx.principal_type == "api_credential" else None,
    }


def _activity_profile_json(profile: ActivityProfile | None) -> dict:
    if profile is None:
        return {
            "status": "learning",
            "activity_type": "unknown",
            "activity_label": "Dati insufficienti",
            "confidence": 0.0,
            "document_count": 0,
            "line_count": 0,
            "evidence": {},
            "field_profile": {},
        }
    return {
        "id": profile.id,
        "status": profile.status,
        "activity_type": profile.activity_type,
        "activity_label": profile.activity_label,
        "confidence": profile.confidence,
        "document_count": profile.document_count,
        "line_count": profile.line_count,
        "human_confirmed": profile.human_confirmed,
        "confirmed_at": profile.confirmed_at.isoformat() if profile.confirmed_at else None,
        "evidence": json.loads(profile.evidence_json or "{}"),
        "field_profile": json.loads(profile.field_profile_json or "{}"),
        "updated_at": profile.updated_at.isoformat(),
    }


def _rule_proposal_json(proposal: RuleProposal) -> dict:
    return {
        "id": proposal.id,
        "rule_code": proposal.rule_code,
        "title": proposal.title,
        "description": proposal.description,
        "rationale": proposal.rationale,
        "confidence": proposal.confidence,
        "status": proposal.status,
        "requires_confirmation": proposal.status == "needs_confirmation",
        "parameters": json.loads(proposal.parameters_json or "{}"),
        "evidence": json.loads(proposal.evidence_json or "{}"),
        "source": proposal.source,
        "confirmed_at": proposal.confirmed_at.isoformat() if proposal.confirmed_at else None,
        "updated_at": proposal.updated_at.isoformat(),
    }


def _discovery_run_json(run: DiscoveryRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "activity_type": run.activity_type,
        "activity_confidence": run.activity_confidence,
        "document_count": run.document_count,
        "line_count": run.line_count,
        "proposed_rules": run.proposed_rules,
        "auto_activated_rules": run.auto_activated_rules,
        "uncertain_rules": run.uncertain_rules,
        "details": json.loads(run.details_json or "{}"),
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


_cors_origins = [
    origin.strip()
    for origin in os.getenv("THISTINTI_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
]


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    path = request.url.path
    supplied_request_id = request.headers.get("x-request-id", "").strip()
    request_id = (
        supplied_request_id[:120] if supplied_request_id and supplied_request_id.isascii() else str(uuid.uuid4())
    )
    request.state.request_id = request_id
    started = time.perf_counter()
    unsafe_method = request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
    origin = request.headers.get("origin")
    if unsafe_method and origin and origin not in _cors_origins:
        return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
    cookie_session = request.cookies.get(settings.session_cookie_name)
    bearer_session = request.headers.get("authorization", "").lower().startswith("bearer ")
    csrf_exempt = path in {"/api/auth/login", "/api/auth/register"}
    if unsafe_method and cookie_session and not bearer_session and not csrf_exempt:
        csrf_cookie = request.cookies.get(settings.csrf_cookie_name, "")
        csrf_header = request.headers.get("x-csrf-token", "")
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
    rate_limited_uploads = {
        "/api/documents/upload",
        "/api/documents/batch",
        "/api/jobs/documents",
        "/api/jobs/batches",
    }
    if path in {"/api/auth/login", "/api/auth/register"} or path in rate_limited_uploads:
        limit = 12 if path.startswith("/api/auth/") else 20
        window = 60.0
        identity = request.client.host if request.client else "unknown"
        key = f"{identity}:{path}"
        try:
            allowed = _consume_request_rate_limit(key, limit, int(window))
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"detail": "Rate limiting service unavailable"},
                headers={"Retry-After": "5"},
            )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests; retry shortly"},
                headers={"Retry-After": "60"},
            )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
    logger.info(
        "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        path,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    response.headers["Cache-Control"] = "no-store" if path.startswith("/api/") else "no-cache"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-CSRF-Token",
        "X-Session-Mode",
        "Idempotency-Key",
        "X-Request-ID",
    ],
)


def _doc_json(document: Document, supplier: Supplier | None = None, include_lines: bool = False) -> dict:
    payload = {
        "id": document.id,
        "document_type": document.document_type,
        "number": document.number,
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "currency": document.currency,
        "source_filename": document.source_filename,
        "parse_status": document.parse_status,
        "parse_message": document.parse_message,
        "confidence": document.confidence,
        "supplier": supplier.legal_name if supplier else None,
        "created_at": document.created_at.isoformat(),
        "line_count": len(document.lines),
    }
    if include_lines:
        payload["lines"] = [
            {
                "id": line.id,
                "line_no": line.line_no,
                "sku": line.sku,
                "description": line.description,
                "color": line.color,
                "size": line.size,
                "lot": line.lot,
                "unit_of_measure": line.unit_of_measure,
                "quantity": float(line.quantity),
                "unit_price": float(line.unit_price),
                "price_base_quantity": float(line.price_base_quantity),
                "discount_rate": float(line.discount_rate),
                "tax_rate": float(line.tax_rate),
                "line_total": float(line.line_total),
                "canonical_key": line.canonical_key,
                "confidence": line.confidence,
            }
            for line in document.lines
        ]
    return payload


def _case_json(case: DiscrepancyCase) -> dict:
    return {
        "id": case.id,
        "chain_id": case.chain_id,
        "case_type": case.case_type,
        "severity": case.severity,
        "amount_estimate": float(case.amount_estimate),
        "confidence": case.confidence,
        "status": case.status,
        "title": case.title,
        "explanation": case.explanation,
        "recommended_action": case.recommended_action,
        "created_at": case.created_at.isoformat(),
        "evidence": [
            {
                "id": ev.id,
                "document_id": ev.document_id,
                "document_line_id": ev.document_line_id,
                "field_name": ev.field_name,
                "observed_value": ev.observed_value,
                "expected_value": ev.expected_value,
                "note": ev.note,
            }
            for ev in case.evidence
        ],
    }


def _validation_dataset_json(dataset: ValidationDataset, include_schema: bool = False) -> dict:
    payload = {
        "id": dataset.id,
        "name": dataset.name,
        "version": dataset.version,
        "description": dataset.description,
        "status": dataset.status,
        "evidence_level": dataset.evidence_level,
        "automation_eligible": dataset.automation_eligible,
        "created_by": dataset.created_by,
        "created_at": dataset.created_at.isoformat(),
        "updated_at": dataset.updated_at.isoformat(),
    }
    if include_schema:
        payload["schema"] = json.loads(dataset.schema_json)
    return payload


def _validation_run_json(run: ValidationRun, include_details: bool = False) -> dict:
    payload = {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "engine_version": run.engine_version,
        "scenario_count": run.scenario_count,
        "true_positives": run.true_positives,
        "false_positives": run.false_positives,
        "false_negatives": run.false_negatives,
        "precision": run.precision,
        "recall": run.recall,
        "f1_score": run.f1_score,
        "amount_mae": float(run.amount_mae),
        "gate_passed": run.gate_passed,
        "automation_approved": run.automation_approved,
        "automation_approved_by": run.automation_approved_by,
        "automation_approved_at": run.automation_approved_at.isoformat() if run.automation_approved_at else None,
        "error_message": run.error_message,
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
    if include_details:
        payload["details"] = json.loads(run.details_json or "{}")
    return payload


@app.get("/api/health")
def health() -> dict:
    edition = (
        "local" if settings.local_edition else ("self-hosted-reference" if settings.self_hosted_reference else "server")
    )
    return {
        "status": "ok",
        "name": settings.app_name,
        "version": app.version,
        "edition": edition,
        "legal_notice_version": LEGAL_NOTICE_VERSION,
        "telemetry": False,
        "cloud_required": False if settings.local_edition else None,
        "operator_managed": settings.self_hosted_reference,
        "deployment_id": settings.deployment_id if settings.self_hosted_reference else None,
        "managed_service": False,
    }


@app.get("/api/readiness", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}})
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    checks = {
        "database": False,
        "storage_write": False,
        "quarantine_write": False,
        "rejected_write": False,
        "secret_configured": len(settings.secret_key) >= 32
        and not any(x in settings.secret_key.lower() for x in ("change-me", "replace-with")),
        "secure_cookies": settings.environment != "production" or settings.secure_cookies,
        "managed_schema": settings.environment != "production" or not settings.auto_create_schema,
        "asynchronous_ingestion": settings.environment != "production" or settings.async_ingestion_enabled,
        "malware_scanner": not settings.require_malware_scanner,
        "ocr_runtime": (not settings.ocr_enabled or ocr_runtime_available()),
        "worker_heartbeat": not settings.async_ingestion_enabled,
    }
    details: dict[str, object] = {}
    if settings.require_malware_scanner:
        try:
            scan_result = probe_malware_scanner(timeout_seconds=min(5, settings.malware_scan_timeout_seconds))
            checks["malware_scanner"] = scan_result.clean
            details["malware_scanner"] = scan_result.scanner
        except ParseError as exc:
            checks["malware_scanner"] = False
            details["malware_scanner_error"] = str(exc)

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
        if settings.async_ingestion_enabled:
            last_seen = db.scalar(select(func.max(WorkerHeartbeat.last_seen_at)))
            if last_seen is not None:
                normalized = last_seen if last_seen.tzinfo else last_seen.replace(tzinfo=utcnow().tzinfo)
                age_seconds = max(0.0, (utcnow() - normalized).total_seconds())
                details["worker_last_seen_seconds"] = round(age_seconds, 1)
                checks["worker_heartbeat"] = age_seconds <= settings.worker_heartbeat_stale_seconds
            else:
                details["worker_last_seen_seconds"] = None
    except Exception as exc:
        logger.exception("Database readiness failed: %s", exc)

    for name, directory in (
        ("storage_write", settings.storage_dir),
        ("quarantine_write", settings.quarantine_dir),
        ("rejected_write", settings.rejected_dir),
    ):
        probe = directory / ".readiness"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            checks[name] = True
        except Exception as exc:
            logger.exception("%s readiness failed: %s", name, exc)
    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503, content={"ready": ready, "checks": checks, "details": details}
    )


@app.get("/api/system/workers")
def list_workers(ctx: AuthContext = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    workers = list(db.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()).limit(100)))
    now = utcnow()
    return [
        {
            "worker_id": worker.worker_id,
            "hostname": worker.hostname,
            "status": worker.status,
            "version": worker.version,
            "started_at": worker.started_at.isoformat(),
            "last_seen_at": worker.last_seen_at.isoformat(),
            "stale": (
                now
                - (
                    worker.last_seen_at
                    if worker.last_seen_at.tzinfo
                    else worker.last_seen_at.replace(tzinfo=now.tzinfo)
                )
            ).total_seconds()
            > settings.worker_heartbeat_stale_seconds,
        }
        for worker in workers
    ]


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    x_session_mode: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Registration disabled")
    if settings.local_edition:
        if payload.legal_notice_version != LEGAL_NOTICE_VERSION:
            raise HTTPException(status_code=422, detail="Legal notice version not accepted")
        if not payload.accepted_terms or not payload.accepted_specific_clauses:
            raise HTTPException(status_code=422, detail="License, risk notice and specific clauses must be accepted")
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    tenant = Tenant(name=payload.organization_name.strip())
    db.add(tenant)
    db.flush()
    user = User(tenant_id=tenant.id, email=email, password_hash=password_hash, role="admin")
    db.add(user)
    db.flush()
    add_audit(db, tenant.id, "tenant.registered", user.id, "tenant", tenant.id, {"organization": tenant.name})
    return _auth_response(
        db,
        user,
        tenant,
        include_token=x_session_mode == "token",
        status_code=status.HTTP_201_CREATED,
    )


@app.post("/api/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    x_session_mode: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower().strip()))
    password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    valid_password = verify_password(payload.password, password_hash)
    tenant = db.get(Tenant, user.tenant_id) if user else None
    if not user or not user.active or not tenant or tenant.status != "active" or not valid_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    add_audit(db, user.tenant_id, "auth.login", user.id, "user", user.id)
    return _auth_response(
        db,
        user,
        tenant,
        include_token=x_session_mode == "token",
    )


@app.post("/api/auth/logout", response_model=OkResponse)
def logout(ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> JSONResponse:
    if ctx.principal_type != "user_session":
        raise HTTPException(status_code=422, detail="API credentials must be revoked from the administration endpoint")
    revoke_session(db, ctx.session_id, "logout")
    add_audit(db, ctx.tenant_id, "auth.logout", ctx.user_id, "auth_session", ctx.session_id)
    db.commit()
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return response


@app.get("/api/auth/me")
def me(ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    tenant = db.get(Tenant, ctx.tenant_id)
    return {
        "id": ctx.user_id,
        "tenant_id": ctx.tenant_id,
        "email": ctx.email,
        "role": ctx.role,
        "organization": tenant.name if tenant else "",
        "principal_type": ctx.principal_type,
        "scopes": list(ctx.scopes),
    }


@app.get("/api/auth/sessions")
def list_auth_sessions(ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    sessions = list(
        db.scalars(
            select(AuthSession)
            .where(AuthSession.user_id == ctx.user_id, AuthSession.tenant_id == ctx.tenant_id)
            .order_by(AuthSession.created_at.desc())
            .limit(100)
        )
    )
    return [
        {
            "id": session.id,
            "current": session.id == ctx.session_id,
            "active": session.active,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
            "revoke_reason": session.revoke_reason,
        }
        for session in sessions
    ]


@app.delete("/api/auth/sessions/{session_id}")
def revoke_auth_session(
    session_id: str, ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == ctx.user_id,
            AuthSession.tenant_id == ctx.tenant_id,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    revoke_session(db, session.id, "user_revoked")
    add_audit(db, ctx.tenant_id, "auth.session_revoked", ctx.user_id, "auth_session", session.id)
    db.commit()
    return {"ok": True, "current": session.id == ctx.session_id}


@app.get("/api/api-credentials")
def list_api_credentials(ctx: AuthContext = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    credentials = list(
        db.scalars(
            select(ApiCredential)
            .where(ApiCredential.tenant_id == ctx.tenant_id)
            .order_by(ApiCredential.created_at.desc())
            .limit(200)
        )
    )
    return [
        {
            "id": credential.id,
            "name": credential.name,
            "key_prefix": credential.key_prefix,
            "role": credential.role,
            "scopes": json.loads(credential.scopes_json or "[]"),
            "active": credential.active,
            "created_at": credential.created_at.isoformat(),
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
            "revoked_at": credential.revoked_at.isoformat() if credential.revoked_at else None,
        }
        for credential in credentials
    ]


@app.post("/api/api-credentials", status_code=201)
def create_api_credential(
    payload: ApiCredentialCreateRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    scopes = sorted(set(payload.scopes))
    if payload.role == "viewer" and any(scope in {"ingest", "review"} for scope in scopes):
        raise HTTPException(status_code=422, detail="Viewer API credentials can only use the read scope")
    if payload.role == "reviewer" and not scopes:
        raise HTTPException(status_code=422, detail="At least one API scope is required")
    expires_at = payload.expires_at
    if expires_at is not None:
        normalized = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=utcnow().tzinfo)
        if normalized <= utcnow():
            raise HTTPException(status_code=422, detail="API credential expiry must be in the future")
        expires_at = normalized
    credential = ApiCredential(
        id=str(uuid.uuid4()),
        tenant_id=ctx.tenant_id,
        name=payload.name.strip(),
        role=payload.role,
        scopes_json=json.dumps(scopes, ensure_ascii=False),
        created_by=ctx.user_id,
        expires_at=expires_at,
    )
    token = issue_api_credential_secret(credential)
    db.add(credential)
    db.flush()
    add_audit(
        db,
        ctx.tenant_id,
        "api_credential.created",
        ctx.user_id,
        "api_credential",
        credential.id,
        {
            "name": credential.name,
            "role": credential.role,
            "scopes": scopes,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    db.commit()
    return {
        "id": credential.id,
        "name": credential.name,
        "role": credential.role,
        "scopes": scopes,
        "token": token,
        "warning": "This token is shown once and cannot be recovered",
    }


@app.delete("/api/api-credentials/{credential_id}")
def revoke_api_credential(
    credential_id: str, ctx: AuthContext = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    credential = db.scalar(
        select(ApiCredential).where(ApiCredential.id == credential_id, ApiCredential.tenant_id == ctx.tenant_id)
    )
    if credential is None:
        raise HTTPException(status_code=404, detail="API credential not found")
    credential.active = False
    credential.revoked_at = utcnow()
    add_audit(
        db,
        ctx.tenant_id,
        "api_credential.revoked",
        ctx.user_id,
        "api_credential",
        credential.id,
        {"name": credential.name},
    )
    db.commit()
    return {"ok": True}


@app.get("/api/users")
def list_users(ctx: AuthContext = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    users = list(db.scalars(select(User).where(User.tenant_id == ctx.tenant_id).order_by(User.created_at)))
    return [
        {"id": u.id, "email": u.email, "role": u.role, "active": u.active, "created_at": u.created_at.isoformat()}
        for u in users
    ]


@app.post("/api/users", status_code=201)
def create_user(
    payload: UserCreateRequest, ctx: AuthContext = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = User(tenant_id=ctx.tenant_id, email=email, password_hash=password_hash, role=payload.role)
    db.add(user)
    db.flush()
    add_audit(db, ctx.tenant_id, "user.created", ctx.user_id, "user", user.id, {"email": email, "role": payload.role})
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role, "active": user.active}


@app.patch("/api/users/{user_id}/status")
def update_user_status(
    user_id: str, payload: UserStatusRequest, ctx: AuthContext = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == ctx.tenant_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == ctx.user_id and not payload.active:
        raise HTTPException(status_code=422, detail="You cannot disable your own active account")
    if user.role == "admin" and user.active and not payload.active and _active_admin_count(db, ctx.tenant_id) <= 1:
        raise HTTPException(status_code=422, detail="At least one active administrator is required")
    if user.active != payload.active:
        user.active = payload.active
        user.token_version += 1
    add_audit(db, ctx.tenant_id, "user.status_changed", ctx.user_id, "user", user.id, {"active": payload.active})
    db.commit()
    return {"ok": True, "active": user.active}


@app.patch("/api/users/{user_id}/role")
def update_user_role(
    user_id: str,
    payload: UserRoleRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == ctx.tenant_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == ctx.user_id and user.role != payload.role:
        raise HTTPException(status_code=422, detail="You cannot change your own administrator role")
    if user.role == "admin" and payload.role != "admin" and user.active and _active_admin_count(db, ctx.tenant_id) <= 1:
        raise HTTPException(status_code=422, detail="At least one active administrator is required")
    if user.role != payload.role:
        previous = user.role
        user.role = payload.role
        user.token_version += 1
        add_audit(
            db,
            ctx.tenant_id,
            "user.role_changed",
            ctx.user_id,
            "user",
            user.id,
            {"previous": previous, "role": payload.role},
        )
    db.commit()
    return {"ok": True, "role": user.role}


@app.post("/api/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: str,
    payload: AdminPasswordResetRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(User).where(User.id == user_id, User.tenant_id == ctx.tenant_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    add_audit(db, ctx.tenant_id, "user.password_reset", ctx.user_id, "user", user.id)
    db.commit()
    return {"ok": True}


@app.post("/api/auth/change-password")
def change_password(
    payload: PasswordChangeRequest, ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    user = db.get(User, ctx.user_id)
    if not user or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    add_audit(db, ctx.tenant_id, "user.password_changed", ctx.user_id, "user", user.id)
    db.commit()
    return {"ok": True}


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> DashboardResponse:
    docs = (
        db.scalar(
            select(func.count(Document.id)).where(Document.tenant_id == ctx.tenant_id, Document.archived.is_(False))
        )
        or 0
    )
    open_cases = (
        db.scalar(
            select(func.count(DiscrepancyCase.id)).where(
                DiscrepancyCase.tenant_id == ctx.tenant_id,
                DiscrepancyCase.status.in_(["open", "needs_review", "confirmed"]),
            )
        )
        or 0
    )
    chains = db.scalar(select(func.count(OperationChain.id)).where(OperationChain.tenant_id == ctx.tenant_id)) or 0
    amount = (
        db.scalar(
            select(func.coalesce(func.sum(DiscrepancyCase.amount_estimate), 0.0)).where(
                DiscrepancyCase.tenant_id == ctx.tenant_id,
                DiscrepancyCase.status.in_(["open", "needs_review", "confirmed"]),
            )
        )
        or 0.0
    )
    failed = (
        db.scalar(
            select(func.count(Document.id)).where(
                Document.tenant_id == ctx.tenant_id, Document.parse_status == "failed"
            )
        )
        or 0
    )
    avg = (
        db.scalar(select(func.coalesce(func.avg(Document.confidence), 0.0)).where(Document.tenant_id == ctx.tenant_id))
        or 0.0
    )
    return DashboardResponse(
        documents=docs,
        cases_open=open_cases,
        chains=chains,
        amount_potential=float(amount),
        parsing_failures=failed,
        confidence_average=float(avg),
    )


async def _stage_upload(file: UploadFile, *, allowed_suffixes: set[str]) -> tuple[Path, str, int]:
    original_name = Path(file.filename or "upload.bin").name[:500] or "upload.bin"
    suffix = Path(original_name).suffix.lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="Unsupported file format")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    tenant_agnostic_name = f"{secrets.token_hex(16)}{suffix}"
    staged_path = settings.quarantine_dir / tenant_agnostic_name
    total = 0
    try:
        with staged_path.open("xb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB")
                destination.write(chunk)
    except Exception:
        staged_path.unlink(missing_ok=True)
        raise
    if total == 0:
        staged_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Empty files are not accepted")
    return staged_path, original_name, total


@app.post("/api/jobs/documents", status_code=202, response_model=ProcessingJobEnvelopeResponse)
async def enqueue_document_upload(
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None),
    supplier_name: str | None = Form(default=None),
    number: str | None = Form(default=None),
    document_date: str | None = Form(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> JSONResponse:
    allowed_types = {"proposal", "order", "confirmation", "delivery", "invoice", "payment", "return", "credit_note"}
    if document_type and document_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Invalid document type")
    staged_path, original_name, size = await _stage_upload(
        file, allowed_suffixes={".xml", ".p7m", ".json", ".csv", ".xlsx", ".xlsm", ".pdf"}
    )
    job, created = enqueue_job(
        db,
        tenant_id=ctx.tenant_id,
        **_job_requester(ctx),
        job_type="ingest_document",
        idempotency_key=idempotency_key,
        input_payload={
            "staged_path": str(staged_path),
            "original_filename": original_name,
            "content_type": file.content_type,
            "size_bytes": size,
            "overrides": {
                "document_type": document_type,
                "supplier_name": supplier_name,
                "number": number,
                "document_date": document_date,
            },
        },
    )
    if not created:
        staged_path.unlink(missing_ok=True)
    else:
        add_audit(
            db,
            ctx.tenant_id,
            "job.queued",
            ctx.user_id,
            "processing_job",
            job.id,
            {"job_type": job.job_type, "filename": original_name, "size_bytes": size},
        )
    db.commit()
    return JSONResponse(status_code=202, content={"job": job_json(job), "created": created})


@app.post("/api/jobs/batches", status_code=202, response_model=ProcessingJobEnvelopeResponse)
async def enqueue_batch_upload(
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> JSONResponse:
    staged_path, original_name, size = await _stage_upload(file, allowed_suffixes={".zip"})
    job, created = enqueue_job(
        db,
        tenant_id=ctx.tenant_id,
        **_job_requester(ctx),
        job_type="ingest_batch",
        idempotency_key=idempotency_key,
        input_payload={
            "staged_path": str(staged_path),
            "original_filename": original_name,
            "content_type": file.content_type,
            "size_bytes": size,
        },
    )
    if not created:
        staged_path.unlink(missing_ok=True)
    else:
        add_audit(
            db,
            ctx.tenant_id,
            "job.queued",
            ctx.user_id,
            "processing_job",
            job.id,
            {"job_type": job.job_type, "filename": original_name, "size_bytes": size},
        )
    db.commit()
    return JSONResponse(status_code=202, content={"job": job_json(job), "created": created})


@app.post(
    "/api/jobs/documents/{document_id}/reprocess",
    status_code=202,
    response_model=ProcessingJobEnvelopeResponse,
)
def enqueue_document_reprocess(
    document_id: str,
    payload: ReprocessRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> JSONResponse:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.tenant_id == ctx.tenant_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    job, created = enqueue_job(
        db,
        tenant_id=ctx.tenant_id,
        **_job_requester(ctx),
        job_type="reprocess_document",
        idempotency_key=idempotency_key,
        input_payload={
            "document_id": document.id,
            "overrides": {
                "document_type": payload.document_type,
                "supplier_name": payload.supplier_name,
                "number": payload.number,
                "document_date": payload.document_date.isoformat() if payload.document_date else None,
            },
        },
    )
    if created:
        add_audit(
            db,
            ctx.tenant_id,
            "job.queued",
            ctx.user_id,
            "processing_job",
            job.id,
            {"job_type": job.job_type, "document_id": document.id},
        )
    db.commit()
    return JSONResponse(status_code=202, content={"job": job_json(job), "created": created})


@app.post("/api/jobs/reanalyze", status_code=202, response_model=ProcessingJobEnvelopeResponse)
def enqueue_tenant_reanalysis(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> JSONResponse:
    job, created = enqueue_job(
        db,
        tenant_id=ctx.tenant_id,
        **_job_requester(ctx),
        job_type="reanalyze_tenant",
        idempotency_key=idempotency_key,
        input_payload={},
        priority=120,
    )
    if created:
        add_audit(
            db,
            ctx.tenant_id,
            "job.queued",
            ctx.user_id,
            "processing_job",
            job.id,
            {"job_type": job.job_type},
        )
    db.commit()
    return JSONResponse(status_code=202, content={"job": job_json(job), "created": created})


@app.post("/api/jobs/red-team", status_code=202, response_model=ProcessingJobEnvelopeResponse)
def enqueue_tenant_red_team(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> JSONResponse:
    job, created = enqueue_job(
        db,
        tenant_id=ctx.tenant_id,
        **_job_requester(ctx),
        job_type="red_team_tenant",
        idempotency_key=idempotency_key,
        input_payload={},
        priority=150,
    )
    if created:
        add_audit(
            db,
            ctx.tenant_id,
            "job.queued",
            ctx.user_id,
            "processing_job",
            job.id,
            {"job_type": job.job_type},
        )
    db.commit()
    return JSONResponse(status_code=202, content={"job": job_json(job), "created": created})


@app.get("/api/jobs")
def list_jobs(
    job_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(ProcessingJob).where(ProcessingJob.tenant_id == ctx.tenant_id)
    count_stmt = select(func.count(ProcessingJob.id)).where(ProcessingJob.tenant_id == ctx.tenant_id)
    if job_status:
        stmt = stmt.where(ProcessingJob.status == job_status)
        count_stmt = count_stmt.where(ProcessingJob.status == job_status)
    total = int(db.scalar(count_stmt) or 0)
    jobs = list(db.scalars(stmt.order_by(ProcessingJob.created_at.desc()).offset(offset).limit(limit)))
    return {"items": [job_json(job) for job in jobs], "total": total, "limit": limit, "offset": offset}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.tenant_id == ctx.tenant_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_json(job)


@app.delete("/api/jobs/{job_id}")
def cancel_job(job_id: str, ctx: AuthContext = Depends(require_reviewer), db: Session = Depends(get_db)) -> dict:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.tenant_id == ctx.tenant_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "queued":
        raise HTTPException(status_code=409, detail="Only queued jobs can be cancelled")
    job.status = "cancelled"
    job.completed_at = utcnow()
    try:
        staged = json.loads(job.input_json or "{}").get("staged_path")
        if staged:
            Path(staged).unlink(missing_ok=True)
    except (ValueError, OSError):
        logger.warning("Unable to remove staged file for cancelled job %s", job.id)
    add_audit(db, ctx.tenant_id, "job.cancelled", ctx.user_id, "processing_job", job.id)
    db.commit()
    return {"ok": True, "job": job_json(job)}


@app.post("/api/documents/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None),
    supplier_name: str | None = Form(default=None),
    number: str | None = Form(default=None),
    document_date: str | None = Form(default=None),
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_synchronous_ingestion_allowed()
    allowed_types = {"proposal", "order", "confirmation", "delivery", "invoice", "payment", "return", "credit_note"}
    if document_type and document_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Invalid document type")
    suffix = Path(file.filename or "upload.bin").suffix.lower()
    allowed_suffixes = {".xml", ".p7m", ".json", ".csv", ".xlsx", ".xlsm", ".pdf"}
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="Unsupported file format")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    total = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = Path(tmp.name)
        try:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB")
                tmp.write(chunk)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    if total == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Empty files are not accepted")
    try:
        try:
            document, outcome = ingest_path(
                db,
                ctx.tenant_id,
                temp_path,
                file.filename or temp_path.name,
                file.content_type,
                {
                    "document_type": document_type,
                    "supplier_name": supplier_name,
                    "number": number,
                    "document_date": document_date,
                },
            )
        except ParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        add_audit(
            db,
            ctx.tenant_id,
            "document.uploaded",
            ctx.user_id,
            "document",
            document.id,
            {"outcome": outcome, "filename": file.filename},
        )
        discovery_run = maybe_run_discovery(db, ctx.tenant_id, ctx.user_id)
        reanalyzed = _reanalyze_tenant_chains(db, ctx.tenant_id) if discovery_run else 0
        db.commit()
        supplier = db.get(Supplier, document.supplier_id) if document.supplier_id else None
        return {
            "document": _doc_json(document, supplier, include_lines=True),
            "outcome": outcome,
            "discovery": _discovery_run_json(discovery_run) if discovery_run else None,
            "reanalyzed_chains": reanalyzed,
        }
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/documents/batch", status_code=201)
async def upload_document_batch(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_synchronous_ingestion_allowed()
    filename = Path(file.filename or "batch.zip").name
    if Path(filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=415, detail="Batch upload requires a ZIP archive")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    total = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        archive_path = Path(tmp.name)
        try:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f"Archive exceeds {settings.max_upload_mb} MB")
                tmp.write(chunk)
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise
    if total == 0:
        archive_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Empty archives are not accepted")

    supported = {".xml", ".p7m", ".json", ".csv", ".xlsx", ".xlsm", ".pdf"}
    results: list[dict] = []
    try:
        try:
            archive = zipfile.ZipFile(archive_path)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=422, detail="Invalid ZIP archive") from exc
        with archive, tempfile.TemporaryDirectory(prefix="thistinti-batch-") as extract_dir:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if not infos:
                raise HTTPException(status_code=422, detail="ZIP archive contains no files")
            if len(infos) > 200:
                raise HTTPException(status_code=422, detail="ZIP archive contains more than 200 files")
            if any(info.flag_bits & 0x1 for info in infos):
                raise HTTPException(status_code=422, detail="Encrypted ZIP members are not supported")
            compressed = sum(max(info.compress_size, 1) for info in infos)
            uncompressed = sum(info.file_size for info in infos)
            if uncompressed > 250 * 1024 * 1024 or uncompressed / compressed > 120:
                raise HTTPException(status_code=422, detail="ZIP archive has an unsafe expansion ratio")

            root = Path(extract_dir)
            for index, info in enumerate(infos, start=1):
                member_path = Path(info.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    results.append({"filename": info.filename, "outcome": "rejected", "error": "unsafe path"})
                    continue
                original_name = member_path.name
                suffix = Path(original_name).suffix.lower()
                if suffix not in supported:
                    results.append({"filename": info.filename, "outcome": "skipped", "error": "unsupported format"})
                    continue
                target = root / f"{index:03d}-{original_name}"
                with archive.open(info) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                savepoint = db.begin_nested()
                try:
                    document, outcome = ingest_path(
                        db,
                        ctx.tenant_id,
                        target,
                        original_name,
                        mimetypes.guess_type(original_name)[0],
                        {},
                    )
                    savepoint.commit()
                    results.append(
                        {
                            "filename": info.filename,
                            "document_id": document.id,
                            "parse_status": document.parse_status,
                            "outcome": outcome or "ingested",
                            "message": document.parse_message,
                        }
                    )
                except Exception as exc:
                    savepoint.rollback()
                    results.append(
                        {
                            "filename": info.filename,
                            "outcome": "failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
        counts = {
            "ingested": sum(result.get("outcome") == "ingested" for result in results),
            "duplicates": sum(result.get("outcome") == "duplicate" for result in results),
            "parse_failed": sum(result.get("outcome") == "parse_failed" for result in results),
            "skipped": sum(result.get("outcome") in {"skipped", "rejected"} for result in results),
            "failed": sum(result.get("outcome") == "failed" for result in results),
        }
        add_audit(
            db,
            ctx.tenant_id,
            "document.batch_uploaded",
            ctx.user_id,
            "tenant",
            ctx.tenant_id,
            {"filename": filename, "files": len(results), **counts},
        )
        discovery_run = maybe_run_discovery(db, ctx.tenant_id, ctx.user_id)
        reanalyzed = _reanalyze_tenant_chains(db, ctx.tenant_id) if discovery_run else 0
        db.commit()
        return {
            "filename": filename,
            "files": len(results),
            "counts": counts,
            "results": results,
            "discovery": _discovery_run_json(discovery_run) if discovery_run else None,
            "reanalyzed_chains": reanalyzed,
        }
    finally:
        archive_path.unlink(missing_ok=True)


@app.get("/api/documents")
def list_documents(
    parse_status: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(Document)
        .options(selectinload(Document.lines))
        .where(Document.tenant_id == ctx.tenant_id, Document.archived.is_(False))
    )
    if parse_status:
        stmt = stmt.where(Document.parse_status == parse_status)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    docs = list(db.scalars(stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)))
    supplier_ids = {d.supplier_id for d in docs if d.supplier_id}
    suppliers = (
        {s.id: s for s in db.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))} if supplier_ids else {}
    )
    return [_doc_json(doc, suppliers.get(doc.supplier_id)) for doc in docs]


@app.get("/api/documents/{document_id}")
def get_document(document_id: str, ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.lines))
        .where(Document.id == document_id, Document.tenant_id == ctx.tenant_id)
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    supplier = db.get(Supplier, document.supplier_id) if document.supplier_id else None
    return _doc_json(document, supplier, include_lines=True)


@app.post("/api/documents/{document_id}/reprocess")
def reprocess_existing_document(
    document_id: str,
    payload: ReprocessRequest,
    ctx: AuthContext = Depends(require_ingest),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_synchronous_ingestion_allowed()
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.lines))
        .where(Document.id == document_id, Document.tenant_id == ctx.tenant_id)
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
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
        document.parse_message = f"Rielaborazione non applicata: {exc}"
        add_audit(
            db, ctx.tenant_id, "document.reprocess_failed", ctx.user_id, "document", document.id, {"error": str(exc)}
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_audit(db, ctx.tenant_id, "document.reprocessed", ctx.user_id, "document", document.id)
    db.commit()
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.lines))
        .where(Document.id == document.id, Document.tenant_id == ctx.tenant_id)
        .execution_options(populate_existing=True)
    )
    supplier = db.get(Supplier, document.supplier_id) if document and document.supplier_id else None
    return _doc_json(document, supplier, include_lines=True)


@app.get(
    "/api/documents/{document_id}/file",
    response_class=FileResponse,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def download_document(document_id: str, ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)):
    document = db.scalar(select(Document).where(Document.id == document_id, Document.tenant_id == ctx.tenant_id))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(document.storage_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Stored file unavailable")
    return FileResponse(path, filename=document.source_filename, media_type=document.mime_type)


@app.post("/api/documents/{document_id}/archive")
def archive_document(
    document_id: str, ctx: AuthContext = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.tenant_id == ctx.tenant_id))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    document.archived = True
    add_audit(db, ctx.tenant_id, "document.archived", ctx.user_id, "document", document.id)
    db.commit()
    return {"ok": True}


@app.get("/api/chains")
def list_chains(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    chains = list(
        db.scalars(
            select(OperationChain)
            .where(OperationChain.tenant_id == ctx.tenant_id)
            .order_by(OperationChain.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    chain_ids = [chain.id for chain in chains]
    links_by_chain: dict[str, list[ChainDocument]] = defaultdict(list)
    if chain_ids:
        links = db.scalars(
            select(ChainDocument)
            .where(
                ChainDocument.tenant_id == ctx.tenant_id,
                ChainDocument.chain_id.in_(chain_ids),
            )
            .order_by(ChainDocument.chain_id, ChainDocument.role, ChainDocument.sequence_no)
        )
        for link in links:
            links_by_chain[link.chain_id].append(link)
    output = []
    for chain in chains:
        documents_by_role: dict[str, list[str]] = {}
        for link in links_by_chain[chain.id]:
            documents_by_role.setdefault(link.role, []).append(link.document_id)
        output.append(
            {
                "id": chain.id,
                "reference_key": chain.reference_key,
                "status": chain.status,
                "confidence": chain.confidence,
                "documents": documents_by_role,
                "updated_at": chain.updated_at.isoformat(),
            }
        )
    return output


@app.get("/api/chains/{chain_id}")
def get_chain_detail(
    chain_id: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    chain = db.scalar(
        select(OperationChain).where(
            OperationChain.id == chain_id,
            OperationChain.tenant_id == ctx.tenant_id,
        )
    )
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    comparison = build_chain_comparison(db, chain)
    cases = list(
        db.scalars(
            select(DiscrepancyCase)
            .options(selectinload(DiscrepancyCase.evidence))
            .where(
                DiscrepancyCase.tenant_id == ctx.tenant_id,
                DiscrepancyCase.chain_id == chain.id,
            )
            .order_by(DiscrepancyCase.created_at.desc())
        )
    )
    return {
        "id": chain.id,
        "reference_key": chain.reference_key,
        "status": chain.status,
        "confidence": chain.confidence,
        "created_at": chain.created_at.isoformat(),
        "updated_at": chain.updated_at.isoformat(),
        "comparison": comparison,
        "cases": [_case_json(case) for case in cases],
        "intelligence": build_intelligence_bundle(db, chain),
    }


@app.get("/api/intelligence/pattern-pack", response_model=AnonymousPatternPackResponse)
def get_anonymous_pattern_pack(
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AnonymousPatternPackResponse:
    return AnonymousPatternPackResponse.model_validate(build_anonymous_pattern_pack(db, ctx.tenant_id))


@app.get("/api/chains/{chain_id}/intelligence", response_model=ChainIntelligenceResponse)
def get_chain_intelligence(
    chain_id: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> ChainIntelligenceResponse:
    chain = db.scalar(
        select(OperationChain).where(
            OperationChain.id == chain_id,
            OperationChain.tenant_id == ctx.tenant_id,
        )
    )
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    return ChainIntelligenceResponse.model_validate(build_intelligence_bundle(db, chain))


@app.post("/api/chains/{chain_id}/simulate", response_model=RiskAssessmentResponse)
def simulate_chain_action(
    chain_id: str,
    payload: IntelligenceSimulationRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> RiskAssessmentResponse:
    chain = db.scalar(
        select(OperationChain).where(
            OperationChain.id == chain_id,
            OperationChain.tenant_id == ctx.tenant_id,
        )
    )
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    result = assess_risk(db, chain, payload.action)
    add_audit(
        db,
        ctx.tenant_id,
        "chain.action_simulated",
        ctx.user_id,
        "operation_chain",
        chain.id,
        {"action": payload.action, "decision": result["decision"], "score": result["score"]},
    )
    db.commit()
    return RiskAssessmentResponse.model_validate(result)


@app.post("/api/chains/{chain_id}/red-team", response_model=RedTeamResponse)
def red_team_chain(
    chain_id: str,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> RedTeamResponse:
    chain = db.scalar(
        select(OperationChain).where(
            OperationChain.id == chain_id,
            OperationChain.tenant_id == ctx.tenant_id,
        )
    )
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    result = run_self_red_team(db, chain)
    add_audit(
        db,
        ctx.tenant_id,
        "chain.red_team_run",
        ctx.user_id,
        "operation_chain",
        chain.id,
        {"status": result["status"], "coverage": result["coverage"]},
    )
    db.commit()
    return RedTeamResponse.model_validate(result)


@app.post("/api/chains/{chain_id}/attach")
def attach_chain_document(
    chain_id: str,
    payload: ChainAttachRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    chain = db.scalar(
        select(OperationChain).where(OperationChain.id == chain_id, OperationChain.tenant_id == ctx.tenant_id)
    )
    document = db.scalar(
        select(Document).where(Document.id == payload.document_id, Document.tenant_id == ctx.tenant_id)
    )
    if not chain or not document:
        raise HTTPException(status_code=404, detail="Chain or document not found")
    if document.document_type != payload.role:
        raise HTTPException(status_code=422, detail="Role must match document type")
    if chain.supplier_id and not document.supplier_id:
        raise HTTPException(status_code=422, detail="Document supplier must be resolved before attachment")
    if chain.supplier_id and document.supplier_id and chain.supplier_id != document.supplier_id:
        raise HTTPException(status_code=409, detail="Document supplier does not match chain supplier")
    if not chain.supplier_id and document.supplier_id:
        chain.supplier_id = document.supplier_id
    existing = db.scalar(
        select(ChainDocument).where(
            ChainDocument.tenant_id == ctx.tenant_id,
            ChainDocument.document_id == document.id,
        )
    )
    if existing and existing.chain_id != chain.id:
        raise HTTPException(status_code=409, detail="Document already belongs to another chain; detach it first")
    if not existing:
        count = (
            db.scalar(
                select(func.count(ChainDocument.id)).where(
                    ChainDocument.chain_id == chain.id, ChainDocument.role == payload.role
                )
            )
            or 0
        )
        db.add(
            ChainDocument(
                tenant_id=ctx.tenant_id,
                chain_id=chain.id,
                document_id=document.id,
                role=payload.role,
                sequence_no=int(count) + 1,
                match_confidence=1.0,
                match_reason="manual",
            )
        )
        primary_field = {
            "proposal": "proposal_document_id",
            "order": "order_document_id",
            "confirmation": "confirmation_document_id",
            "delivery": "delivery_document_id",
            "invoice": "invoice_document_id",
            "payment": "payment_document_id",
            "return": "return_document_id",
            "credit_note": "credit_note_document_id",
        }[payload.role]
        if not getattr(chain, primary_field):
            setattr(chain, primary_field, document.id)
    analyze_chain(db, chain)
    add_audit(
        db,
        ctx.tenant_id,
        "chain.document_attached",
        ctx.user_id,
        "operation_chain",
        chain.id,
        {"document_id": document.id, "role": payload.role},
    )
    db.commit()
    return {"ok": True}


@app.delete("/api/chains/{chain_id}/documents/{document_id}")
def detach_chain_document(
    chain_id: str,
    document_id: str,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    link = db.scalar(
        select(ChainDocument).where(
            ChainDocument.tenant_id == ctx.tenant_id,
            ChainDocument.chain_id == chain_id,
            ChainDocument.document_id == document_id,
        )
    )
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    chain = db.get(OperationChain, chain_id)
    role = link.role
    db.delete(link)
    db.flush()
    if chain:
        primary_field = {
            "proposal": "proposal_document_id",
            "order": "order_document_id",
            "confirmation": "confirmation_document_id",
            "delivery": "delivery_document_id",
            "invoice": "invoice_document_id",
            "payment": "payment_document_id",
            "return": "return_document_id",
            "credit_note": "credit_note_document_id",
        }[role]
        if getattr(chain, primary_field) == document_id:
            replacement = db.scalar(
                select(ChainDocument.document_id)
                .where(ChainDocument.chain_id == chain.id, ChainDocument.role == role)
                .order_by(ChainDocument.sequence_no)
            )
            setattr(chain, primary_field, replacement)
        analyze_chain(db, chain)
    add_audit(
        db,
        ctx.tenant_id,
        "chain.document_detached",
        ctx.user_id,
        "operation_chain",
        chain_id,
        {"document_id": document_id},
    )
    db.commit()
    return {"ok": True}


@app.post("/api/chains/{chain_id}/analyze")
def reanalyze_chain(chain_id: str, ctx: AuthContext = Depends(require_reviewer), db: Session = Depends(get_db)) -> dict:
    chain = db.scalar(
        select(OperationChain).where(OperationChain.id == chain_id, OperationChain.tenant_id == ctx.tenant_id)
    )
    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")
    cases = analyze_chain(db, chain)
    add_audit(db, ctx.tenant_id, "chain.analyzed", ctx.user_id, "operation_chain", chain.id, {"cases": len(cases)})
    db.commit()
    return {"cases": len(cases), "status": chain.status}


@app.get("/api/cases")
def list_cases(
    case_status: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(DiscrepancyCase)
        .options(selectinload(DiscrepancyCase.evidence))
        .where(DiscrepancyCase.tenant_id == ctx.tenant_id)
    )
    if case_status:
        stmt = stmt.where(DiscrepancyCase.status == case_status)
    if severity:
        stmt = stmt.where(DiscrepancyCase.severity == severity)
    cases = list(db.scalars(stmt.order_by(DiscrepancyCase.created_at.desc()).offset(offset).limit(limit)))
    return [_case_json(case) for case in cases]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    case = db.scalar(
        select(DiscrepancyCase)
        .options(selectinload(DiscrepancyCase.evidence))
        .where(
            DiscrepancyCase.id == case_id,
            DiscrepancyCase.tenant_id == ctx.tenant_id,
        )
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_json(case)


@app.post("/api/cases/{case_id}/decision")
def review_case(
    case_id: str, payload: ReviewRequest, ctx: AuthContext = Depends(require_reviewer), db: Session = Depends(get_db)
) -> dict:
    case = db.scalar(
        select(DiscrepancyCase).where(DiscrepancyCase.id == case_id, DiscrepancyCase.tenant_id == ctx.tenant_id)
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.status = payload.decision
    db.add(
        ReviewDecision(
            tenant_id=ctx.tenant_id, case_id=case.id, user_id=ctx.user_id, decision=payload.decision, note=payload.note
        )
    )
    add_audit(
        db,
        ctx.tenant_id,
        "case.reviewed",
        ctx.user_id,
        "discrepancy_case",
        case.id,
        {"decision": payload.decision, "note": payload.note},
    )
    db.commit()
    return {"ok": True, "status": case.status}


@app.get("/api/audit")
def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == ctx.tenant_id)
            .order_by(AuditEvent.sequence_no.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return [
        {
            "id": e.id,
            "sequence_no": e.sequence_no,
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "actor_id": e.actor_id,
            "payload": json.loads(e.payload_json or "{}"),
            "previous_hash": e.previous_hash,
            "event_hash": e.event_hash,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@app.get("/api/audit/verify")
def verify_audit(
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return verify_audit_chain(db, ctx.tenant_id)


@app.post("/api/demo/load")
def load_demo(ctx: AuthContext = Depends(require_reviewer), db: Session = Depends(get_db)) -> dict:
    sample_dir = Path(__file__).resolve().parents[1] / "samples"
    files = [
        sample_dir / "order.json",
        sample_dir / "delivery.json",
        sample_dir / "invoice.json",
        sample_dir / "return.json",
    ]
    results = []
    for path in files:
        if not path.exists():
            continue
        document, outcome = ingest_path(db, ctx.tenant_id, path, path.name, "application/json", {})
        results.append({"id": document.id, "outcome": outcome})
    discovery_run = maybe_run_discovery(db, ctx.tenant_id, ctx.user_id)
    reanalyzed = _reanalyze_tenant_chains(db, ctx.tenant_id) if discovery_run else 0
    add_audit(db, ctx.tenant_id, "demo.loaded", ctx.user_id, "tenant", ctx.tenant_id, {"files": len(results)})
    db.commit()
    return {
        "loaded": len(results),
        "results": results,
        "discovery": _discovery_run_json(discovery_run) if discovery_run else None,
        "reanalyzed_chains": reanalyzed,
    }


@app.get("/api/item-aliases")
def list_item_aliases(
    limit: int = Query(default=200, ge=1, le=1000),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    aliases = list(
        db.scalars(
            select(ItemAlias)
            .where(ItemAlias.tenant_id == ctx.tenant_id)
            .order_by(ItemAlias.confirmed_count.desc(), ItemAlias.normalized_alias)
            .limit(limit)
        )
    )
    return [
        {
            "id": alias.id,
            "supplier_id": alias.supplier_id,
            "canonical_key": alias.canonical_key,
            "alias": alias.alias,
            "normalized_alias": alias.normalized_alias,
            "confirmed_count": alias.confirmed_count,
        }
        for alias in aliases
    ]


@app.post("/api/item-aliases/confirm", status_code=201)
def confirm_item_alias(
    payload: ItemAliasConfirmRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    canonical_line = db.scalar(
        select(DocumentLine).where(
            DocumentLine.id == payload.canonical_line_id,
            DocumentLine.tenant_id == ctx.tenant_id,
        )
    )
    alias_line = db.scalar(
        select(DocumentLine).where(
            DocumentLine.id == payload.alias_line_id,
            DocumentLine.tenant_id == ctx.tenant_id,
        )
    )
    if not canonical_line or not alias_line:
        raise HTTPException(status_code=404, detail="Document line not found")
    if canonical_line.id == alias_line.id:
        raise HTTPException(status_code=422, detail="Choose two different lines")
    canonical_document = db.get(Document, canonical_line.document_id)
    alias_document = db.get(Document, alias_line.document_id)
    if not canonical_document or not alias_document:
        raise HTTPException(status_code=404, detail="Source document not found")
    supplier_ids = {value for value in (canonical_document.supplier_id, alias_document.supplier_id) if value}
    if len(supplier_ids) > 1:
        raise HTTPException(status_code=422, detail="Lines from different suppliers cannot share an alias")
    supplier_id = next(iter(supplier_ids), None)
    canonical_key = canonical_line.canonical_key
    if not canonical_key:
        raise HTTPException(status_code=422, detail="Canonical line has no normalized key")

    stored: list[ItemAlias] = []
    tokens = list(dict.fromkeys(alias_tokens(alias_line) + alias_tokens(canonical_line)))
    for token in tokens:
        supplier_predicate = ItemAlias.supplier_id == supplier_id if supplier_id else ItemAlias.supplier_id.is_(None)
        item = db.scalar(
            select(ItemAlias).where(
                ItemAlias.tenant_id == ctx.tenant_id,
                supplier_predicate,
                ItemAlias.normalized_alias == token,
            )
        )
        if item is None:
            item = ItemAlias(
                tenant_id=ctx.tenant_id,
                supplier_id=supplier_id,
                canonical_key=canonical_key,
                alias=alias_line.sku or alias_line.description or token,
                normalized_alias=token,
                confirmed_count=1,
            )
            db.add(item)
        else:
            item.canonical_key = canonical_key
            item.confirmed_count += 1
        stored.append(item)
    db.flush()

    document_ids = [canonical_line.document_id, alias_line.document_id]
    chain_ids = set(
        db.scalars(
            select(ChainDocument.chain_id).where(
                ChainDocument.tenant_id == ctx.tenant_id,
                ChainDocument.document_id.in_(document_ids),
            )
        )
    )
    for chain_id in chain_ids:
        chain = db.get(OperationChain, chain_id)
        if chain and chain.tenant_id == ctx.tenant_id:
            analyze_chain(db, chain)
    add_audit(
        db,
        ctx.tenant_id,
        "item_alias.confirmed",
        ctx.user_id,
        "document_line",
        alias_line.id,
        {
            "canonical_line_id": canonical_line.id,
            "canonical_key": canonical_key,
            "supplier_id": supplier_id,
            "tokens": tokens,
            "reanalyzed_chains": len(chain_ids),
        },
    )
    db.commit()
    return {
        "ok": True,
        "canonical_key": canonical_key,
        "aliases": [
            {
                "id": item.id,
                "normalized_alias": item.normalized_alias,
                "confirmed_count": item.confirmed_count,
            }
            for item in stored
        ],
        "reanalyzed_chains": len(chain_ids),
    }


@app.get("/api/validation/datasets")
def list_validation_datasets(
    include_archived: bool = Query(default=False),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(ValidationDataset).where(ValidationDataset.tenant_id == ctx.tenant_id)
    if not include_archived:
        stmt = stmt.where(ValidationDataset.status == "active")
    datasets = list(db.scalars(stmt.order_by(ValidationDataset.created_at.desc())))
    run_counts = {
        dataset_id: count
        for dataset_id, count in db.execute(
            select(ValidationRun.dataset_id, func.count(ValidationRun.id))
            .where(ValidationRun.tenant_id == ctx.tenant_id)
            .group_by(ValidationRun.dataset_id)
        )
    }
    result = []
    for dataset in datasets:
        item = _validation_dataset_json(dataset)
        item["run_count"] = int(run_counts.get(dataset.id, 0))
        result.append(item)
    return result


@app.post("/api/validation/datasets", status_code=201)
def create_validation_dataset(
    payload: ValidationDatasetPayload,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    schema_json = json.dumps(payload.model_dump(), ensure_ascii=False, separators=(",", ":"), default=str)
    if len(schema_json.encode("utf-8")) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Validation dataset exceeds 5 MB")
    existing = db.scalar(
        select(ValidationDataset).where(
            ValidationDataset.tenant_id == ctx.tenant_id,
            ValidationDataset.name == payload.name.strip(),
            ValidationDataset.version == payload.version.strip(),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Dataset name and version already exist")
    dataset = ValidationDataset(
        tenant_id=ctx.tenant_id,
        name=payload.name.strip(),
        version=payload.version.strip(),
        description=payload.description,
        evidence_level=payload.evidence_level,
        automation_eligible=False,
        schema_json=schema_json,
        created_by=ctx.user_id,
    )
    db.add(dataset)
    db.flush()
    add_audit(
        db,
        ctx.tenant_id,
        "validation.dataset_created",
        ctx.user_id,
        "validation_dataset",
        dataset.id,
        {
            "name": dataset.name,
            "version": dataset.version,
            "scenarios": len(payload.scenarios),
            "evidence_level": dataset.evidence_level,
            "automation_eligible": dataset.automation_eligible,
        },
    )
    db.commit()
    return _validation_dataset_json(dataset, include_schema=True)


@app.get("/api/validation/datasets/{dataset_id}")
def get_validation_dataset(
    dataset_id: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    dataset = db.scalar(
        select(ValidationDataset).where(
            ValidationDataset.id == dataset_id, ValidationDataset.tenant_id == ctx.tenant_id
        )
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Validation dataset not found")
    return _validation_dataset_json(dataset, include_schema=True)


@app.patch("/api/validation/datasets/{dataset_id}/status")
def set_validation_dataset_status(
    dataset_id: str,
    payload: ValidationDatasetStatusRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    dataset = db.scalar(
        select(ValidationDataset).where(
            ValidationDataset.id == dataset_id, ValidationDataset.tenant_id == ctx.tenant_id
        )
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Validation dataset not found")
    dataset.status = payload.status
    if payload.status == "archived":
        dataset.automation_eligible = False
    add_audit(
        db,
        ctx.tenant_id,
        "validation.dataset_status_changed",
        ctx.user_id,
        "validation_dataset",
        dataset.id,
        {"status": payload.status},
    )
    db.commit()
    return {"ok": True, "status": dataset.status}


@app.post(
    "/api/validation/datasets/{dataset_id}/automation",
    response_model=ValidationAutomationApprovalResponse,
)
def set_validation_automation_approval(
    dataset_id: str,
    payload: ValidationAutomationApprovalRequest,
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ValidationAutomationApprovalResponse:
    dataset = db.scalar(
        select(ValidationDataset).where(
            ValidationDataset.id == dataset_id,
            ValidationDataset.tenant_id == ctx.tenant_id,
        )
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Validation dataset not found")
    latest = db.scalar(
        select(ValidationRun)
        .where(
            ValidationRun.tenant_id == ctx.tenant_id,
            ValidationRun.dataset_id == dataset.id,
            ValidationRun.status == "completed",
        )
        .order_by(ValidationRun.completed_at.desc(), ValidationRun.created_at.desc())
    )
    if payload.enabled:
        if dataset.status != "active":
            raise HTTPException(status_code=409, detail="Archived validation datasets cannot authorize automation")
        if dataset.evidence_level == "synthetic":
            raise HTTPException(status_code=422, detail="Synthetic validation cannot authorize automation")
        if latest is None or not latest.gate_passed:
            raise HTTPException(status_code=409, detail="A successful validation gate is required before approval")
        if latest.scenario_count < MIN_AUTOMATION_VALIDATION_SCENARIOS:
            raise HTTPException(
                status_code=409,
                detail=f"At least {MIN_AUTOMATION_VALIDATION_SCENARIOS} validation scenarios are required",
            )
        if latest.engine_version != RELEASE_VERSION:
            raise HTTPException(status_code=409, detail="Validation must be rerun with the current engine version")
    dataset.automation_eligible = payload.enabled
    if latest is not None:
        latest.automation_approved = payload.enabled
        latest.automation_approved_by = ctx.user_id if payload.enabled else None
        latest.automation_approved_at = utcnow() if payload.enabled else None
        latest.automation_approval_note = payload.note if payload.enabled else None
    add_audit(
        db,
        ctx.tenant_id,
        "validation.automation_approved" if payload.enabled else "validation.automation_revoked",
        ctx.user_id,
        "validation_dataset",
        dataset.id,
        {
            "evidence_level": dataset.evidence_level,
            "validation_run_id": latest.id if latest else None,
            "note": payload.note,
        },
    )
    db.commit()
    return ValidationAutomationApprovalResponse(
        ok=True,
        dataset_id=dataset.id,
        automation_eligible=dataset.automation_eligible,
        evidence_level=dataset.evidence_level,
        validation_run_id=latest.id if latest else None,
    )


@app.post("/api/validation/datasets/{dataset_id}/run", status_code=201)
def execute_validation_dataset(
    dataset_id: str,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    dataset = db.scalar(
        select(ValidationDataset).where(
            ValidationDataset.id == dataset_id,
            ValidationDataset.tenant_id == ctx.tenant_id,
            ValidationDataset.status == "active",
        )
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Active validation dataset not found")
    try:
        payload = ValidationDatasetPayload.model_validate(json.loads(dataset.schema_json))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Stored validation dataset is invalid: {exc}") from exc
    run = run_validation_dataset(db, dataset, payload, ctx.user_id)
    add_audit(
        db,
        ctx.tenant_id,
        "validation.run_completed" if run.status == "completed" else "validation.run_failed",
        ctx.user_id,
        "validation_run",
        run.id,
        {
            "dataset_id": dataset.id,
            "engine_version": ENGINE_VERSION,
            "gate_passed": run.gate_passed,
            "precision": run.precision,
            "recall": run.recall,
            "f1": run.f1_score,
        },
    )
    db.commit()
    return _validation_run_json(run, include_details=True)


@app.get("/api/validation/runs")
def list_validation_runs(
    dataset_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(ValidationRun).where(ValidationRun.tenant_id == ctx.tenant_id)
    if dataset_id:
        stmt = stmt.where(ValidationRun.dataset_id == dataset_id)
    runs = list(db.scalars(stmt.order_by(ValidationRun.created_at.desc()).limit(limit)))
    return [_validation_run_json(run) for run in runs]


@app.get("/api/validation/runs/{run_id}")
def get_validation_run(
    run_id: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    run = db.scalar(select(ValidationRun).where(ValidationRun.id == run_id, ValidationRun.tenant_id == ctx.tenant_id))
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return _validation_run_json(run, include_details=True)


@app.get("/api/validation/runs/{run_id}/report")
def export_validation_run_report(
    run_id: str,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    redacted: bool = Query(default=True),
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> Response:
    run = db.scalar(
        select(ValidationRun)
        .options(selectinload(ValidationRun.dataset))
        .where(ValidationRun.id == run_id, ValidationRun.tenant_id == ctx.tenant_id)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    if not redacted and ctx.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required for internal validation reports")
    report = build_validation_report(run.dataset, run, redacted=redacted)
    if redacted:
        safe_name = report["dataset"]["reference"]
    else:
        safe_name = (
            "".join(
                character if character.isalnum() or character in "-_" else "-" for character in run.dataset.name
            ).strip("-")[:80]
            or "dataset"
        )
    suffix = "redacted" if redacted else "internal"
    if format == "markdown":
        content = render_validation_report_markdown(report)
        media_type = "text/markdown; charset=utf-8"
        extension = "md"
    else:
        content = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        media_type = "application/json"
        extension = "json"
    add_audit(
        db,
        ctx.tenant_id,
        "validation.report_exported",
        ctx.user_id,
        "validation_run",
        run.id,
        {
            "dataset_id": run.dataset_id,
            "dataset_reference": report["dataset"]["reference"],
            "format": format,
            "redacted": redacted,
            "report_schema": report["schema"],
        },
    )
    db.commit()
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="validation-{safe_name}-{suffix}.{extension}"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/api/validation/load-default", status_code=201)
def load_default_validation_dataset(
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    path = Path(__file__).resolve().parents[1] / "samples" / "validation_core.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="Default validation dataset is missing")
    payload = ValidationDatasetPayload.model_validate_json(path.read_text(encoding="utf-8"))
    existing = db.scalar(
        select(ValidationDataset).where(
            ValidationDataset.tenant_id == ctx.tenant_id,
            ValidationDataset.name == payload.name,
            ValidationDataset.version == payload.version,
        )
    )
    if existing:
        return _validation_dataset_json(existing, include_schema=True)
    dataset = ValidationDataset(
        tenant_id=ctx.tenant_id,
        name=payload.name,
        version=payload.version,
        description=payload.description,
        evidence_level=payload.evidence_level,
        automation_eligible=False,
        schema_json=json.dumps(payload.model_dump(), ensure_ascii=False, separators=(",", ":"), default=str),
        created_by=ctx.user_id,
    )
    db.add(dataset)
    db.flush()
    add_audit(
        db,
        ctx.tenant_id,
        "validation.default_loaded",
        ctx.user_id,
        "validation_dataset",
        dataset.id,
        {"name": dataset.name, "version": dataset.version},
    )
    db.commit()
    return _validation_dataset_json(dataset, include_schema=True)


@app.get("/api/discovery/profile")
def get_discovery_profile(
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    profile = db.scalar(select(ActivityProfile).where(ActivityProfile.tenant_id == ctx.tenant_id))
    rules = list(
        db.scalars(
            select(RuleProposal)
            .where(RuleProposal.tenant_id == ctx.tenant_id)
            .order_by(RuleProposal.status, RuleProposal.confidence.desc(), RuleProposal.title)
        )
    )
    return {
        "profile": _activity_profile_json(profile),
        "summary": {
            "total_rules": len(rules),
            "active_rules": sum(rule.status in {"auto_active", "confirmed"} for rule in rules),
            "questions": sum(rule.status == "needs_confirmation" for rule in rules),
            "rejected_rules": sum(rule.status == "rejected" for rule in rules),
        },
    }


@app.post("/api/discovery/run", status_code=201)
def execute_discovery(
    payload: DiscoveryRunRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    if payload.confirmation_threshold >= payload.auto_activate_threshold:
        raise HTTPException(
            status_code=422, detail="Confirmation threshold must be lower than auto-activation threshold"
        )
    run = run_discovery(
        db,
        ctx.tenant_id,
        ctx.user_id,
        DiscoverySettings(
            minimum_documents=payload.minimum_documents,
            auto_activate_threshold=payload.auto_activate_threshold,
            confirmation_threshold=payload.confirmation_threshold,
            force_relearn=payload.force_relearn,
        ),
    )
    reanalyzed = _reanalyze_tenant_chains(db, ctx.tenant_id)
    add_audit(
        db,
        ctx.tenant_id,
        "discovery.completed",
        ctx.user_id,
        "discovery_run",
        run.id,
        {
            "activity_type": run.activity_type,
            "confidence": run.activity_confidence,
            "auto_activated_rules": run.auto_activated_rules,
            "uncertain_rules": run.uncertain_rules,
            "reanalyzed_chains": reanalyzed,
        },
    )
    db.commit()
    return {"run": _discovery_run_json(run), "reanalyzed_chains": reanalyzed}


@app.post("/api/discovery/profile/decision")
def decide_activity_profile(
    payload: ActivityProfileDecisionRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    profile = db.scalar(select(ActivityProfile).where(ActivityProfile.tenant_id == ctx.tenant_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Activity profile not found; run discovery first")
    if payload.decision == "corrected":
        if not payload.activity_type or not payload.activity_label:
            raise HTTPException(status_code=422, detail="Corrected profiles require activity_type and activity_label")
        profile.activity_type = payload.activity_type.strip()
        profile.activity_label = payload.activity_label.strip()
    if payload.decision == "relearn":
        profile.human_confirmed = False
        profile.confirmed_by = None
        profile.confirmed_at = None
        profile.status = "learning"
        run = run_discovery(
            db,
            ctx.tenant_id,
            ctx.user_id,
            DiscoverySettings(force_relearn=True),
        )
    else:
        profile.human_confirmed = True
        profile.confirmed_by = ctx.user_id
        profile.confirmed_at = utcnow()
        profile.confidence = max(profile.confidence, 0.99)
        profile.status = "ready"
        run = None
    add_audit(
        db,
        ctx.tenant_id,
        "discovery.profile_decided",
        ctx.user_id,
        "activity_profile",
        profile.id,
        {
            "decision": payload.decision,
            "activity_type": profile.activity_type,
            "activity_label": profile.activity_label,
        },
    )
    db.commit()
    return {"profile": _activity_profile_json(profile), "run": _discovery_run_json(run) if run else None}


@app.get("/api/discovery/runs")
def list_discovery_runs(
    limit: int = Query(default=30, ge=1, le=200),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    runs = list(
        db.scalars(
            select(DiscoveryRun)
            .where(DiscoveryRun.tenant_id == ctx.tenant_id)
            .order_by(DiscoveryRun.created_at.desc())
            .limit(limit)
        )
    )
    return [_discovery_run_json(run) for run in runs]


@app.get("/api/discovery/rules")
def list_discovered_rules(
    status_filter: str | None = Query(default=None, alias="status"),
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(RuleProposal).where(RuleProposal.tenant_id == ctx.tenant_id)
    if status_filter:
        stmt = stmt.where(RuleProposal.status == status_filter)
    rules = list(db.scalars(stmt.order_by(RuleProposal.confidence.desc(), RuleProposal.title)))
    return [_rule_proposal_json(rule) for rule in rules]


@app.post("/api/discovery/rules/{rule_id}/decision")
def decide_discovered_rule(
    rule_id: str,
    payload: RuleDecisionRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    proposal = db.scalar(
        select(RuleProposal).where(RuleProposal.id == rule_id, RuleProposal.tenant_id == ctx.tenant_id)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Rule proposal not found")
    proposal.status = payload.decision
    proposal.confirmed_by = ctx.user_id
    proposal.confirmed_at = utcnow()
    reanalyzed = _reanalyze_tenant_chains(db, ctx.tenant_id)
    add_audit(
        db,
        ctx.tenant_id,
        "discovery.rule_decided",
        ctx.user_id,
        "rule_proposal",
        proposal.id,
        {"decision": payload.decision, "note": payload.note, "reanalyzed_chains": reanalyzed},
    )
    db.commit()
    return {"rule": _rule_proposal_json(proposal), "reanalyzed_chains": reanalyzed}


@app.get(
    "/api/export",
    response_class=FileResponse,
    responses={200: {"content": {"application/zip": {}}}},
)
def export_tenant(
    include_files: bool = Query(default=False),
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    documents = list(
        db.scalars(select(Document).options(selectinload(Document.lines)).where(Document.tenant_id == ctx.tenant_id))
    )
    cases = list(
        db.scalars(
            select(DiscrepancyCase)
            .options(selectinload(DiscrepancyCase.evidence))
            .where(DiscrepancyCase.tenant_id == ctx.tenant_id)
        )
    )
    chains = list(db.scalars(select(OperationChain).where(OperationChain.tenant_id == ctx.tenant_id)))
    audit_events = list(db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == ctx.tenant_id)))
    payload = {
        "export_version": 1,
        "tenant_id": ctx.tenant_id,
        "documents": [
            _doc_json(d, db.get(Supplier, d.supplier_id) if d.supplier_id else None, include_lines=True)
            for d in documents
        ],
        "chains": [
            {"id": c.id, "reference_key": c.reference_key, "status": c.status, "confidence": c.confidence}
            for c in chains
        ],
        "cases": [_case_json(c) for c in cases],
        "audit": [
            {
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "payload": json.loads(e.payload_json or "{}"),
                "previous_hash": e.previous_hash,
                "event_hash": e.event_hash,
                "created_at": e.created_at.isoformat(),
            }
            for e in audit_events
        ],
    }
    export_handle = tempfile.NamedTemporaryFile(prefix="thistinti-export-", suffix=".zip", delete=False)
    export_path = Path(export_handle.name)
    export_handle.close()
    try:
        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("export.json", json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            if include_files:
                for document in documents:
                    path = Path(document.storage_path)
                    if path.exists() and path.is_file():
                        safe_source_name = Path(document.source_filename).name
                        archive.write(path, arcname=f"files/{document.id}/{safe_source_name}")
        add_audit(
            db, ctx.tenant_id, "tenant.exported", ctx.user_id, "tenant", ctx.tenant_id, {"include_files": include_files}
        )
        db.commit()
        return FileResponse(
            export_path,
            filename="thistinti-export.zip",
            media_type="application/zip",
            background=BackgroundTask(export_path.unlink, missing_ok=True),
        )
    except Exception:
        export_path.unlink(missing_ok=True)
        raise


static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
