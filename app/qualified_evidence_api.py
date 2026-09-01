from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.background import BackgroundTask

from .audit import add_audit
from .db import get_db
from .models import AuditEvent, DiscrepancyCase, Document, OperationChain, Supplier
from .security import AuthContext, current_user, require_admin
from .services.evidence_integrity import canonical_document_evidence_bytes

router = APIRouter()


def _legacy_api():
    from . import api

    return api


@router.get(
    "/api/documents/{document_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def download_qualified_document(
    document_id: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.tenant_id == ctx.tenant_id))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    payload = canonical_document_evidence_bytes(db, document)
    if payload is None:
        raise HTTPException(status_code=410, detail="Canonical document evidence unavailable or invalid")
    safe_name = Path(document.source_filename).name.replace('"', "") or "document.bin"
    return Response(
        content=payload,
        media_type=document.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get(
    "/api/export",
    response_class=FileResponse,
    responses={200: {"content": {"application/zip": {}}}},
)
def export_qualified_tenant(
    include_files: bool = Query(default=False),
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    api = _legacy_api()
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
            api._doc_json(
                document,
                db.get(Supplier, document.supplier_id) if document.supplier_id else None,
                include_lines=True,
            )
            for document in documents
        ],
        "chains": [
            {
                "id": chain.id,
                "reference_key": chain.reference_key,
                "status": chain.status,
                "confidence": chain.confidence,
            }
            for chain in chains
        ],
        "cases": [api._case_json(case) for case in cases],
        "audit": [
            {
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "payload": json.loads(event.payload_json or "{}"),
                "previous_hash": event.previous_hash,
                "event_hash": event.event_hash,
                "created_at": event.created_at.isoformat(),
            }
            for event in audit_events
        ],
    }

    canonical_files: list[tuple[str, bytes]] = []
    if include_files:
        for document in documents:
            evidence_bytes = canonical_document_evidence_bytes(db, document)
            if evidence_bytes is None:
                raise HTTPException(
                    status_code=410,
                    detail=f"Canonical evidence unavailable or invalid for document {document.id}",
                )
            safe_source_name = Path(document.source_filename).name
            canonical_files.append((f"files/{document.id}/{safe_source_name}", evidence_bytes))

    export_handle = tempfile.NamedTemporaryFile(prefix="thistinti-export-", suffix=".zip", delete=False)
    export_path = Path(export_handle.name)
    export_handle.close()
    try:
        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("export.json", json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            for arcname, evidence_bytes in canonical_files:
                archive.writestr(arcname, evidence_bytes)
        add_audit(
            db,
            ctx.tenant_id,
            "tenant.exported",
            ctx.user_id,
            "tenant",
            ctx.tenant_id,
            {"include_files": include_files, "evidence_source": "canonical" if include_files else "metadata_only"},
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
