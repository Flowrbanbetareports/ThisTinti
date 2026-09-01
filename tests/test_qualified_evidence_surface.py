from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from app.db import SessionLocal
from app.models import Document
from app.services.evidence_integrity import canonical_document_evidence_matches_hash


def test_sealed_evidence_is_identical_in_download_and_export_after_storage_replacement(client, auth, tmp_path):
    loaded = client.post("/api/demo/load", headers=auth)
    assert loaded.status_code == 200, loaded.text
    document_json = client.get("/api/documents?limit=1", headers=auth).json()[0]

    with SessionLocal() as db:
        document = db.get(Document, document_json["id"])
        storage_path = Path(document.storage_path)
        original = storage_path.read_bytes()
        source_filename = document.source_filename
        assert canonical_document_evidence_matches_hash(db, document) is True
        db.commit()

    replacement = b"substituted reviewer-facing bytes"
    replacement_path = tmp_path / "replacement.bin"
    replacement_path.write_bytes(replacement)
    os.replace(replacement_path, storage_path)
    try:
        downloaded = client.get(f"/api/documents/{document_json['id']}/file", headers=auth)
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.content == original
        assert downloaded.content != replacement

        exported = client.get("/api/export?include_files=true", headers=auth)
        assert exported.status_code == 200, exported.text
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            exported_bytes = archive.read(f"files/{document_json['id']}/{Path(source_filename).name}")
        assert exported_bytes == original
        assert exported_bytes == downloaded.content
    finally:
        storage_path.write_bytes(original)


def test_unsealed_invalid_storage_fails_closed_for_download_and_export(client, auth):
    loaded = client.post("/api/demo/load", headers=auth)
    assert loaded.status_code == 200, loaded.text
    document_json = client.get("/api/documents?limit=1", headers=auth).json()[0]

    with SessionLocal() as db:
        document = db.get(Document, document_json["id"])
        storage_path = Path(document.storage_path)
        original = storage_path.read_bytes()

    storage_path.write_bytes(b"substituted-before-seal")
    try:
        assert client.get(f"/api/documents/{document_json['id']}/file", headers=auth).status_code == 410
        assert client.get("/api/export?include_files=true", headers=auth).status_code == 410
    finally:
        storage_path.write_bytes(original)
