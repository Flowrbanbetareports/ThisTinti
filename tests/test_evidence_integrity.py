from __future__ import annotations

import hashlib

from app.models import Document
from app.services.evidence_integrity import stored_document_bytes_match_hash


def _document_for(path, payload: bytes) -> Document:
    return Document(
        storage_path=str(path),
        file_hash=hashlib.sha256(payload).hexdigest(),
    )


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
