from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Document
from ..provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceOrigin


def stored_document_bytes_match_hash(document: Document) -> bool:
    """Return True only when the stored file bytes still match Document.file_hash.

    Missing/unreadable storage, malformed hashes, directories, and byte substitutions
    are all treated as unavailable evidence and therefore fail closed.
    """
    expected = (document.file_hash or "").strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        return False

    storage_path = (document.storage_path or "").strip()
    if not storage_path:
        return False
    path = Path(storage_path)
    try:
        if not path.is_file():
            return False
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hexdigest(), expected)


def finding_document_evidence_bytes_are_current(
    db: Session,
    *,
    finding: ProvenanceFinding,
) -> bool:
    """Verify stored bytes for every DOCUMENT_EVIDENCE fact supporting a finding.

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
        if not stored_document_bytes_match_hash(document):
            return False
    return True
