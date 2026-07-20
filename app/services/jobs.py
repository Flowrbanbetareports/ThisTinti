from __future__ import annotations

import json
import mimetypes
import shutil
import socket
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import add_audit
from ..config import settings
from ..db import set_tenant_context
from ..models import AuthSession, Document, OperationChain, ProcessingJob, RateLimitCounter, WorkerHeartbeat, utcnow
from ..parsers import ParseError
from ..version import RELEASE_VERSION
from .discovery import maybe_run_discovery
from .ingestion import ingest_path, reprocess_document
from .rules import analyze_chain
from .intelligence import run_self_red_team

SUPPORTED_SUFFIXES = {".xml", ".p7m", ".json", ".csv", ".xlsx", ".xlsm", ".pdf"}


def touch_worker(db: Session, worker_id: str, status: str = "active") -> WorkerHeartbeat:
    heartbeat = db.get(WorkerHeartbeat, worker_id)
    if heartbeat is None:
        heartbeat = WorkerHeartbeat(
            worker_id=worker_id,
            hostname=socket.gethostname(),
            status=status,
            version=RELEASE_VERSION,
        )
        db.add(heartbeat)
    heartbeat.status = status
    heartbeat.last_seen_at = utcnow()
    heartbeat.version = RELEASE_VERSION
    db.flush()
    return heartbeat


def run_maintenance(db: Session) -> dict[str, int]:
    now = utcnow()
    expired_sessions = list(
        db.scalars(select(AuthSession).where(AuthSession.active.is_(True), AuthSession.expires_at < now))
    )
    for session in expired_sessions:
        session.active = False
        session.revoked_at = now
        session.revoke_reason = "expired"

    job_cutoff = now - timedelta(days=max(1, settings.completed_job_retention_days))
    deleted_jobs = (
        db.execute(
            delete(ProcessingJob).where(
                ProcessingJob.status.in_(("completed", "failed", "cancelled")),
                ProcessingJob.completed_at.is_not(None),
                ProcessingJob.completed_at < job_cutoff,
            )
        ).rowcount
        or 0
    )

    heartbeat_cutoff = now - timedelta(days=7)
    deleted_heartbeats = (
        db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.last_seen_at < heartbeat_cutoff)).rowcount or 0
    )

    deleted_rate_limits = (
        db.execute(delete(RateLimitCounter).where(RateLimitCounter.expires_at < now - timedelta(hours=1))).rowcount or 0
    )

    removed_quarantine = 0
    file_cutoff = now.timestamp() - max(1, settings.quarantine_retention_hours) * 3600
    for path in settings.quarantine_dir.glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < file_cutoff:
                path.unlink()
                removed_quarantine += 1
        except OSError:
            continue
    db.flush()
    return {
        "expired_sessions": len(expired_sessions),
        "deleted_jobs": int(deleted_jobs),
        "deleted_heartbeats": int(deleted_heartbeats),
        "deleted_rate_limits": int(deleted_rate_limits),
        "removed_quarantine": removed_quarantine,
    }


def job_actor_id(job: ProcessingJob) -> str | None:
    return job.created_by or job.created_by_api_credential


def job_json(job: ProcessingJob, include_result: bool = True) -> dict:
    payload = {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "priority": job.priority,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "progress": job.progress,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if include_result:
        payload["result"] = json.loads(job.result_json or "{}")
    return payload


def enqueue_job(
    db: Session,
    *,
    tenant_id: str,
    created_by: str | None,
    created_by_api_credential: str | None = None,
    job_type: str,
    input_payload: dict,
    idempotency_key: str | None = None,
    priority: int = 100,
) -> tuple[ProcessingJob, bool]:
    normalized_key = idempotency_key.strip()[:180] if idempotency_key and idempotency_key.strip() else None
    if normalized_key:
        existing = db.scalar(
            select(ProcessingJob).where(
                ProcessingJob.tenant_id == tenant_id,
                ProcessingJob.idempotency_key == normalized_key,
            )
        )
        if existing:
            return existing, False
    job = ProcessingJob(
        tenant_id=tenant_id,
        created_by=created_by,
        created_by_api_credential=created_by_api_credential,
        job_type=job_type,
        priority=priority,
        max_attempts=settings.worker_max_attempts,
        idempotency_key=normalized_key,
        input_json=json.dumps(input_payload, ensure_ascii=False, default=str),
    )
    savepoint = db.begin_nested()
    db.add(job)
    try:
        db.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()
        if not normalized_key:
            raise
        existing = db.scalar(
            select(ProcessingJob).where(
                ProcessingJob.tenant_id == tenant_id,
                ProcessingJob.idempotency_key == normalized_key,
            )
        )
        if existing:
            return existing, False
        raise
    return job, True


def recover_stale_jobs(db: Session) -> int:
    cutoff = utcnow() - timedelta(seconds=settings.worker_lease_seconds)
    jobs = list(
        db.scalars(
            select(ProcessingJob).where(
                ProcessingJob.status == "running",
                ProcessingJob.locked_at.is_not(None),
                ProcessingJob.locked_at < cutoff,
            )
        )
    )
    for job in jobs:
        job.status = "queued" if job.attempts < job.max_attempts else "failed"
        job.locked_at = None
        job.locked_by = None
        job.available_at = utcnow()
        if job.status == "failed":
            job.error_message = "Worker lease expired too many times"
            job.completed_at = utcnow()
    db.flush()
    return len(jobs)


def claim_next_job(db: Session, worker_id: str | None = None) -> ProcessingJob | None:
    worker = (worker_id or f"{socket.gethostname()}:{id(db)}")[:120]
    recover_stale_jobs(db)
    stmt = (
        select(ProcessingJob)
        .where(ProcessingJob.status == "queued", ProcessingJob.available_at <= utcnow())
        .order_by(ProcessingJob.priority.asc(), ProcessingJob.created_at.asc())
        .limit(1)
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    job = db.scalar(stmt)
    if not job:
        return None
    job.status = "running"
    job.attempts += 1
    job.progress = max(job.progress, 1)
    job.locked_at = utcnow()
    job.locked_by = worker
    job.started_at = job.started_at or utcnow()
    job.error_message = None
    db.flush()
    return job


def _safe_staged_path(value: str) -> Path:
    path = Path(value).resolve()
    root = settings.quarantine_dir.resolve()
    if path != root and root not in path.parents:
        raise ParseError("Percorso job fuori dalla quarantena")
    if not path.is_file():
        raise ParseError("File in quarantena non disponibile")
    return path


def _reanalyze_tenant(db: Session, tenant_id: str) -> int:
    chains = list(db.scalars(select(OperationChain).where(OperationChain.tenant_id == tenant_id)))
    for chain in chains:
        analyze_chain(db, chain)
    return len(chains)


def _red_team_tenant(db: Session, tenant_id: str) -> dict:
    chains = list(db.scalars(select(OperationChain).where(OperationChain.tenant_id == tenant_id)))
    reports = [run_self_red_team(db, chain) for chain in chains]
    weak = sorted(
        (report for report in reports if report["status"] != "pass"),
        key=lambda report: report["coverage"],
    )
    average = sum((report["coverage"] for report in reports), 0.0) / len(reports) if reports else 1.0
    detailed = weak[:100] if weak else sorted(reports, key=lambda report: report["coverage"])[:20]
    return {
        "chains": len(reports),
        "average_coverage": round(average, 4),
        "needs_improvement": len(weak),
        "reports": detailed,
        "reports_omitted": max(0, len(reports) - len(detailed)),
    }


def _process_document(db: Session, job: ProcessingJob, payload: dict) -> dict:
    path = _safe_staged_path(payload["staged_path"])
    job.progress = 10
    document, outcome = ingest_path(
        db,
        job.tenant_id,
        path,
        payload["original_filename"],
        payload.get("content_type"),
        payload.get("overrides") or {},
    )
    job.progress = 75
    add_audit(
        db,
        job.tenant_id,
        "document.async_ingested",
        job_actor_id(job),
        "document",
        document.id,
        {"outcome": outcome or "ingested", "filename": payload["original_filename"], "job_id": job.id},
    )
    discovery = maybe_run_discovery(db, job.tenant_id, job_actor_id(job))
    reanalyzed = _reanalyze_tenant(db, job.tenant_id) if discovery else 0
    return {
        "document_id": document.id,
        "parse_status": document.parse_status,
        "outcome": outcome or "ingested",
        "reanalyzed_chains": reanalyzed,
        "discovery_run_id": discovery.id if discovery else None,
    }


def _batch_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = [info for info in archive.infolist() if not info.is_dir()]
    if not infos:
        raise ParseError("ZIP archive contains no files")
    if len(infos) > settings.max_batch_files:
        raise ParseError(f"ZIP archive contains more than {settings.max_batch_files} files")
    if any(info.flag_bits & 0x1 for info in infos):
        raise ParseError("Encrypted ZIP members are not supported")
    compressed = sum(max(info.compress_size, 1) for info in infos)
    uncompressed = sum(info.file_size for info in infos)
    max_expanded = settings.max_batch_expanded_mb * 1024 * 1024
    if uncompressed > max_expanded or uncompressed / compressed > 120:
        raise ParseError("ZIP archive has an unsafe expansion ratio")
    return infos


def _process_batch(db: Session, job: ProcessingJob, payload: dict) -> dict:
    archive_path = _safe_staged_path(payload["staged_path"])
    results: list[dict] = []
    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as exc:
        raise ParseError("Invalid ZIP archive") from exc
    with archive, tempfile.TemporaryDirectory(prefix="thistinti-worker-batch-") as extract_dir:
        infos = _batch_members(archive)
        root = Path(extract_dir)
        for index, info in enumerate(infos, start=1):
            member_path = Path(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                results.append({"filename": info.filename, "outcome": "rejected", "error": "unsafe path"})
                continue
            original_name = member_path.name
            suffix = Path(original_name).suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:
                results.append({"filename": info.filename, "outcome": "skipped", "error": "unsupported format"})
                continue
            target = root / f"{index:04d}-{original_name}"
            with archive.open(info) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
            savepoint = db.begin_nested()
            try:
                document, outcome = ingest_path(
                    db,
                    job.tenant_id,
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
                    }
                )
            except Exception as exc:
                savepoint.rollback()
                results.append(
                    {"filename": info.filename, "outcome": "failed", "error": f"{type(exc).__name__}: {exc}"}
                )
            job.progress = min(90, 5 + int(index / len(infos) * 80))
    counts = {
        "ingested": sum(result.get("outcome") == "ingested" for result in results),
        "duplicates": sum(result.get("outcome") == "duplicate" for result in results),
        "parse_failed": sum(result.get("outcome") == "parse_failed" for result in results),
        "skipped": sum(result.get("outcome") in {"skipped", "rejected"} for result in results),
        "failed": sum(result.get("outcome") == "failed" for result in results),
    }
    add_audit(
        db,
        job.tenant_id,
        "document.async_batch_ingested",
        job_actor_id(job),
        "processing_job",
        job.id,
        {"filename": payload["original_filename"], "files": len(results), **counts},
    )
    discovery = maybe_run_discovery(db, job.tenant_id, job_actor_id(job))
    reanalyzed = _reanalyze_tenant(db, job.tenant_id) if discovery else 0
    return {"files": len(results), "counts": counts, "results": results, "reanalyzed_chains": reanalyzed}


def _process_reprocess(db: Session, job: ProcessingJob, payload: dict) -> dict:
    document = db.scalar(
        select(Document).where(Document.id == payload["document_id"], Document.tenant_id == job.tenant_id)
    )
    if document is None:
        raise ParseError("Documento da rielaborare non trovato")
    job.progress = 15
    document = reprocess_document(db, document, payload.get("overrides") or {})
    job.progress = 85
    add_audit(
        db,
        job.tenant_id,
        "document.async_reprocessed",
        job_actor_id(job),
        "document",
        document.id,
        {"job_id": job.id},
    )
    discovery = maybe_run_discovery(db, job.tenant_id, job_actor_id(job))
    reanalyzed = _reanalyze_tenant(db, job.tenant_id) if discovery else 0
    return {
        "document_id": document.id,
        "parse_status": document.parse_status,
        "reanalyzed_chains": reanalyzed,
        "discovery_run_id": discovery.id if discovery else None,
    }


def execute_job(db: Session, job: ProcessingJob) -> None:
    set_tenant_context(db, job.tenant_id)
    payload = json.loads(job.input_json or "{}")
    try:
        if job.job_type == "ingest_document":
            result = _process_document(db, job, payload)
        elif job.job_type == "ingest_batch":
            result = _process_batch(db, job, payload)
        elif job.job_type == "reprocess_document":
            result = _process_reprocess(db, job, payload)
        elif job.job_type == "reanalyze_tenant":
            result = {"reanalyzed_chains": _reanalyze_tenant(db, job.tenant_id)}
        elif job.job_type == "red_team_tenant":
            result = _red_team_tenant(db, job.tenant_id)
            add_audit(
                db,
                job.tenant_id,
                "tenant.red_team_completed",
                job_actor_id(job),
                "tenant",
                job.tenant_id,
                {
                    "chains": result["chains"],
                    "average_coverage": result["average_coverage"],
                    "needs_improvement": result["needs_improvement"],
                },
            )
        else:
            raise ValueError(f"Unsupported job type: {job.job_type}")
        job.result_json = json.dumps(result, ensure_ascii=False, default=str)
        job.status = "completed"
        job.progress = 100
        job.completed_at = utcnow()
        job.locked_at = None
        job.locked_by = None
        add_audit(
            db,
            job.tenant_id,
            "job.completed",
            job_actor_id(job),
            "processing_job",
            job.id,
            {"job_type": job.job_type, "attempts": job.attempts},
        )
        db.flush()
        staged = payload.get("staged_path")
        if staged:
            _safe_staged_path(staged).unlink(missing_ok=True)
    except Exception as exc:
        job.error_message = f"{type(exc).__name__}: {exc}"[:4000]
        job.locked_at = None
        job.locked_by = None
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.available_at = utcnow() + timedelta(seconds=min(300, 5 * (2 ** (job.attempts - 1))))
        else:
            job.status = "failed"
            job.completed_at = utcnow()
            staged = payload.get("staged_path")
            if staged:
                try:
                    source = _safe_staged_path(staged)
                    target = settings.rejected_dir / f"{job.id}-{source.name}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source.replace(target)
                    payload["rejected_path"] = str(target)
                    job.input_json = json.dumps(payload, ensure_ascii=False, default=str)
                except (OSError, ParseError):
                    pass
            add_audit(
                db,
                job.tenant_id,
                "job.failed",
                job_actor_id(job),
                "processing_job",
                job.id,
                {"job_type": job.job_type, "attempts": job.attempts, "error": job.error_message},
            )
        db.flush()
