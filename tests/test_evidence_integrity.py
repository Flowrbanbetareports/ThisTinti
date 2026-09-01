from __future__ import annotations

import hashlib
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Document, Tenant
from app.services.evidence_integrity import (
    canonical_document_evidence_bytes,
    canonical_document_evidence_matches_hash,
    document_evidence_snapshots,
    finding_document_evidence_bytes_are_current,
    stored_document_bytes_match_hash,
)
from app.services.judgment_provenance import _finding_matches_case_contract, lock_p1_support_for_update


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


def test_stored_document_bytes_match_hash_fails_closed_on_storage_oserror(tmp_path):
    payload = b"original"
    path = tmp_path / "evidence.json"
    path.write_bytes(payload)
    document = _document_for(path, payload)

    with patch("app.services.evidence_integrity.Path.read_bytes", side_effect=OSError("unreadable")):
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
            document_evidence_snapshots.select().where(document_evidence_snapshots.c.document_id == document.id)
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


def test_canonical_document_evidence_bytes_covers_unsealed_and_sealed_paths(tmp_path):
    original = b'{"amount":100}'
    path = tmp_path / "evidence.json"
    path.write_bytes(original)

    with SessionLocal() as db:
        document = _persisted_document(db, path, original)
        assert canonical_document_evidence_bytes(db, document) == original
        assert canonical_document_evidence_matches_hash(db, document) is True
        path.write_bytes(b'{"amount":999}')
        assert canonical_document_evidence_bytes(db, document) == original


def test_canonical_helpers_reject_invalid_document_identity():
    document = Document(file_hash="not-a-sha256", storage_path="ignored")
    db = MagicMock()

    assert canonical_document_evidence_bytes(db, document) is None
    assert canonical_document_evidence_matches_hash(db, document) is False
    db.execute.assert_not_called()


def test_canonical_snapshot_rejects_malformed_snapshot_hash(tmp_path):
    original = b'{"amount":100}'
    path = tmp_path / "evidence.json"
    path.write_bytes(original)

    with SessionLocal() as db:
        document = _persisted_document(db, path, original)
        db.execute(
            document_evidence_snapshots.insert().values(
                document_id=document.id,
                tenant_id=document.tenant_id,
                file_hash="not-a-sha256",
                evidence_bytes=original,
                sealed_at=document.created_at,
            )
        )
        assert canonical_document_evidence_bytes(db, document) is None
        assert canonical_document_evidence_matches_hash(db, document) is False


def test_canonical_document_evidence_bytes_fails_closed_if_snapshot_disappears():
    document = SimpleNamespace(
        id="document-1",
        tenant_id="tenant-1",
        file_hash="a" * 64,
        storage_path="ignored",
    )
    snapshot_lookup = MagicMock()
    snapshot_lookup.first.return_value = ("document-1",)
    snapshot_read = MagicMock()
    snapshot_read.mappings.return_value.one_or_none.return_value = None
    db = MagicMock()
    db.execute.side_effect = [snapshot_lookup, snapshot_read]

    assert canonical_document_evidence_bytes(db, document) is None


def _finding() -> SimpleNamespace:
    return SimpleNamespace(tenant_id="tenant-1", id="finding-1", rule_id="procurement.duplicate_document_number")


def test_finding_document_evidence_fail_closed_structure_branches():
    finding = _finding()

    db = MagicMock()
    db.scalars.return_value = []
    assert finding_document_evidence_bytes_are_current(db, finding=finding) is False

    db = MagicMock()
    db.scalars.side_effect = [["fact-1"], []]
    assert finding_document_evidence_bytes_are_current(db, finding=finding) is False

    fact = SimpleNamespace(origin_id="origin-1")
    db = MagicMock()
    db.scalars.side_effect = [["fact-1"], [fact], []]
    assert finding_document_evidence_bytes_are_current(db, finding=finding) is False

    origin_without_document = SimpleNamespace(origin_type="DOCUMENT_EVIDENCE", document_id=None)
    db = MagicMock()
    db.scalars.side_effect = [["fact-1"], [fact], [origin_without_document]]
    assert finding_document_evidence_bytes_are_current(db, finding=finding) is False

    origin = SimpleNamespace(origin_type="DOCUMENT_EVIDENCE", document_id="document-1", source_ref="sha256:expected")
    db = MagicMock()
    db.scalars.side_effect = [["fact-1"], [fact], [origin], []]
    assert finding_document_evidence_bytes_are_current(db, finding=finding) is False

    document = SimpleNamespace(id="document-1", file_hash="actual")
    db = MagicMock()
    db.scalars.side_effect = [["fact-1"], [fact], [origin], [document]]
    assert finding_document_evidence_bytes_are_current(db, finding=finding) is False

    matching_origin = SimpleNamespace(
        origin_type="DOCUMENT_EVIDENCE",
        document_id="document-1",
        source_ref="sha256:actual",
    )
    db = MagicMock()
    db.scalars.side_effect = [["fact-1"], [fact], [matching_origin], [document]]
    with patch("app.services.evidence_integrity.canonical_document_evidence_matches_hash", return_value=False):
        assert finding_document_evidence_bytes_are_current(db, finding=finding) is False


def test_judgment_contract_rejects_failed_canonical_evidence_check():
    finding = _finding()
    with patch(
        "app.services.judgment_provenance.finding_document_evidence_bytes_are_current",
        return_value=False,
    ):
        assert (
            _finding_matches_case_contract(MagicMock(), case_type="duplicate_document_number", finding=finding) is False
        )


def test_lock_p1_support_rejects_missing_chain():
    db = MagicMock()
    db.scalar.return_value = None

    assert lock_p1_support_for_update(db, tenant_id="tenant-1", chain_id="chain-1") is False
