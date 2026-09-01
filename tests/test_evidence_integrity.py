from __future__ import annotations

import hashlib
import os

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Document, Tenant
from app.services.evidence_integrity import (
    canonical_document_evidence_matches_hash,
    document_evidence_snapshots,
    stored_document_bytes_match_hash,
)


def _document_for(path, payload: bytes) -> Document:
    return Document(
        storage_path=str(path),
        file_hash=hashlib.sha256(payload).hexdigest(),
    )


def _persisted_document(db, path, payload: bytes) -> Document:
    tenant = Tenant(name="Evidence Integrity Test")
    db.add(tenant)
    db.flush()
    document = Document(
        tenant_id=tenant.id,
        document_type="invoice",
        source_filename=path.name,
        storage_path=str(path),
        file_hash=hashlib.sha256(payload).hexdigest(),
    )
    db.add(document)
    db.flush()
    return document


def test_stored_document_bytes_match_hash_accepts_exact_bytes(tmp_path):
    payload = b'{"document":"qualified-evidence"}'
    path = tmp_path / "evidence.json"
    path.write_bytes(payload)
    document = _document_for(path, payload)

    assert stored_document_bytes_match_hash(document) is True


def test_stored_document_bytes_match_hash_rejects_same_path_byte_substitution(tmp_path):
    original = b'{"amount":100}'
    path = tmp_path / "evidence.json"
    path.write_bytes(original)
    document = _document_for(path, original)

    path.write_bytes(b'{"amount":999}')

    assert stored_document_bytes_match_hash(document) is False


def test_stored_document_bytes_match_hash_rejects_missing_storage(tmp_path):
    payload = b"original"
    document = _document_for(tmp_path / "missing.json", payload)

    assert stored_document_bytes_match_hash(document) is False


def test_stored_document_bytes_match_hash_rejects_malformed_expected_hash(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_bytes(b"original")
    document = Document(storage_path=str(path), file_hash="not-a-sha256")

    assert stored_document_bytes_match_hash(document) is False


def test_stored_document_bytes_match_hash_rejects_directory_storage(tmp_path):
    document = Document(
        storage_path=str(tmp_path),
        file_hash=hashlib.sha256(b"").hexdigest(),
    )

    assert stored_document_bytes_match_hash(document) is False


def test_canonical_snapshot_survives_atomic_filesystem_replacement(tmp_path):
    original = b'{"amount":100}'
    replacement = b'{"amount":999}'
    path = tmp_path / "evidence.json"
    path.write_bytes(original)

    with SessionLocal() as db:
        document = _persisted_document(db, path, original)
        assert canonical_document_evidence_matches_hash(db, document) is True

        replacement_path = tmp_path / "replacement.json"
        replacement_path.write_bytes(replacement)
        os.replace(replacement_path, path)

        assert stored_document_bytes_match_hash(document) is False
        assert canonical_document_evidence_matches_hash(db, document) is True


def test_canonical_snapshot_rejects_substitution_before_first_seal(tmp_path):
    original = b'{"amount":100}'
    path = tmp_path / "evidence.json"
    path.write_bytes(original)

    with SessionLocal() as db:
        document = _persisted_document(db, path, original)
        path.write_bytes(b'{"amount":999}')

        assert canonical_document_evidence_matches_hash(db, document) is False
        snapshot = db.execute(
            document_evidence_snapshots.select().where(
                document_evidence_snapshots.c.document_id == document.id
            )
        ).first()
        assert snapshot is None


def test_canonical_snapshot_fails_closed_if_snapshot_bytes_are_corrupted(tmp_path):
    original = b'{"amount":100}'
    path = tmp_path / "evidence.json"
    path.write_bytes(original)

    with SessionLocal() as db:
        document = _persisted_document(db, path, original)
        assert canonical_document_evidence_matches_hash(db, document) is True
        db.execute(
            update(document_evidence_snapshots)
            .where(document_evidence_snapshots.c.document_id == document.id)
            .values(evidence_bytes=b"corrupted")
        )

        assert canonical_document_evidence_matches_hash(db, document) is False
