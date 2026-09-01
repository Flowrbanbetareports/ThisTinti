from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, ForeignKey, LargeBinary, String, Table, insert, select
from sqlalchemy.orm import Session

from ..models import Document
from ..provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceOrigin


document_evidence_snapshots = Table(
    "document_evidence_snapshots",
    Document.__table__.metadata,
    Column("document_id", String(36), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tenant_id", String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("file_hash", String(64), nullable=False),
    Column("evidence_bytes", LargeBinary, nullable=False),
    Column("sealed_at", DateTime(timezone=True), nullable=False),
)


def _normalized_sha256(value: str | None) -> str | None:
    expected = (value or "").strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        return None
    return expected


def _verified_storage_bytes(document: Document) -> bytes | None:
    expected = _normalized_sha256(document.file_hash)
    storage_path = (document.storage_path or "").strip()
    if expected is None or not storage_path:
        return None
    path = Path(storage_path)
    try:
        if not path.is_file():
            return None
        payload = path.read_bytes()
    except (OSError, ValueError, TypeError):
        return None
    if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), expected):
        return None
    return payload


def _verified_snapshot_bytes(db: Session, document: Document) -> bytes | None:
    expected = _normalized_sha256(document.file_hash)
    if expected is None or not document.id or not document.tenant_id:
        return None
    snapshot = (
        db.execute(
            select(
                document_evidence_snapshots.c.file_hash,
                document_evidence_snapshots.c.evidence_bytes,
            ).where(
                document_evidence_snapshots.c.document_id == document.id,
                document_evidence_snapshots.c.tenant_id == document.tenant_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if snapshot is None:
        return None
    snapshot_hash = _normalized_sha256(snapshot["file_hash"])
    payload = bytes(snapshot["evidence_bytes"])
    if snapshot_hash is None or not hmac.compare_digest(snapshot_hash, expected):
        return None
    if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), expected):
        return None
    return payload


def stored_document_bytes_match_hash(document: Document) -> bool:
    """Return True only when the current filesystem bytes match Document.file_hash.

    This is a physical-storage diagnostic. Qualification decisions use the immutable
    database snapshot once it has been sealed, so an out-of-band filesystem writer
    cannot change the evidence semantics after verification.
    """
    return _verified_storage_bytes(document) is not None


def canonical_document_evidence_bytes(db: Session, document: Document) -> bytes | None:
    """Return the bytes that the product may expose as this document's evidence.

    A sealed snapshot is authoritative and must itself verify against Document.file_hash.
    Before a snapshot exists, mutable storage may be exposed only while its bytes verify.
    This read-only helper never seals evidence; qualification remains the only seal path.
    """
    if _normalized_sha256(document.file_hash) is None or not document.id or not document.tenant_id:
        return None
    snapshot = db.execute(
        select(document_evidence_snapshots.c.document_id).where(
            document_evidence_snapshots.c.document_id == document.id,
            document_evidence_snapshots.c.tenant_id == document.tenant_id,
        )
    ).first()
    if snapshot is not None:
        return _verified_snapshot_bytes(db, document)
    return _verified_storage_bytes(document)


def canonical_document_evidence_matches_hash(db: Session, document: Document) -> bool:
    """Seal or verify transaction-bound canonical bytes for a document.

    The P1 judgment path locks the Document row before calling this function. On the
    first qualified read, bytes are accepted only if they match Document.file_hash
    and are copied into the same database transaction as the judgment. Thereafter
    the snapshot, rather than the mutable filesystem path, is authoritative.
    """
    expected = _normalized_sha256(document.file_hash)
    if expected is None or not document.id or not document.tenant_id:
        return False

    existing = db.execute(
        select(document_evidence_snapshots.c.document_id).where(
            document_evidence_snapshots.c.document_id == document.id,
            document_evidence_snapshots.c.tenant_id == document.tenant_id,
        )
    ).first()
    if existing is not None:
        return _verified_snapshot_bytes(db, document) is not None

    payload = _verified_storage_bytes(document)
    if payload is None:
        return False
    db.execute(
        insert(document_evidence_snapshots).values(
            document_id=document.id,
            tenant_id=document.tenant_id,
            file_hash=expected,
            evidence_bytes=payload,
            sealed_at=datetime.now(timezone.utc),
        )
    )
    return True


def finding_document_evidence_bytes_are_current(
    db: Session,
    *,
    finding: ProvenanceFinding,
) -> bool:
    """Verify canonical bytes for every DOCUMENT_EVIDENCE fact supporting a finding.

    SYSTEM_OBSERVATION and other non-document origins are intentionally outside this
    check. Any malformed or cross-tenant document-evidence reference fails closed.
    """
    fact_ids = list(
        db.scalars(
            select(ProvenanceFindingFact.fact_id).where(
                ProvenanceFindingFact.tenant_id == finding.tenant_id,
                ProvenanceFindingFact.finding_id == finding.id,
            )
        )
    )
    if not fact_ids or len(set(fact_ids)) != len(fact_ids):
        return False

    facts = list(
        db.scalars(
            select(ProvenanceFact).where(
                ProvenanceFact.tenant_id == finding.tenant_id,
                ProvenanceFact.id.in_(fact_ids),
            )
        )
    )
    if len(facts) != len(fact_ids):
        return False

    origin_ids = {fact.origin_id for fact in facts}
    origins = list(
        db.scalars(
            select(ProvenanceOrigin).where(
                ProvenanceOrigin.tenant_id == finding.tenant_id,
                ProvenanceOrigin.id.in_(origin_ids),
            )
        )
    )
    if len(origins) != len(origin_ids):
        return False

    document_origins = [origin for origin in origins if origin.origin_type == "DOCUMENT_EVIDENCE"]
    document_ids = {origin.document_id for origin in document_origins}
    if None in document_ids:
        return False
    if not document_ids:
        return True

    documents = list(
        db.scalars(
            select(Document).where(
                Document.tenant_id == finding.tenant_id,
                Document.id.in_(document_ids),
            )
        )
    )
    by_id = {document.id: document for document in documents}
    if set(by_id) != document_ids:
        return False

    for origin in document_origins:
        document = by_id.get(origin.document_id)
        if document is None:
            return False
        if origin.source_ref != f"sha256:{document.file_hash}":
            return False
        if not canonical_document_evidence_matches_hash(db, document):
            return False
    return True
