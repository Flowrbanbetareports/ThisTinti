from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from scripts.backup_system import _libpq_url, create_backup
from scripts.restore_backup import restore_sqlite, restore_storage
from scripts.verify_backup import verify_backup


def test_consistent_backup_verify_and_restore(client, auth, tmp_path: Path):
    payload = {
        "document_type": "order",
        "number": "BACKUP-PO-1",
        "supplier_name": "Backup Supplier",
        "lines": [{"sku": "B-1", "quantity": 1, "unit_price": 25}],
    }
    uploaded = client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": ("backup-order.json", json.dumps(payload).encode(), "application/json")},
    )
    assert uploaded.status_code == 201, uploaded.text

    bundle = tmp_path / "backup.zip"
    created = create_backup(bundle, include_storage=True)
    assert created["bundle_sha256"]
    verified = verify_backup(bundle)
    assert verified["valid"] is True
    assert verified["database_engine"] == "sqlite"

    restored_database = tmp_path / "restored" / "thistinti.db"
    restored_storage = tmp_path / "restored" / "storage"
    restore_sqlite(bundle, restored_database, restored_storage)
    connection = sqlite3.connect(restored_database)
    try:
        count = connection.execute("SELECT COUNT(*) FROM documents WHERE number = ?", ("BACKUP-PO-1",)).fetchone()[0]
    finally:
        connection.close()
    assert count == 1
    assert any(path.is_file() for path in restored_storage.rglob("*"))


def test_force_restore_replaces_storage_exactly(client, auth, tmp_path: Path):
    bundle = tmp_path / "backup.zip"
    create_backup(bundle, include_storage=True)

    restored_database = tmp_path / "target" / "thistinti.db"
    restored_storage = tmp_path / "target" / "storage"
    restored_database.parent.mkdir(parents=True)
    restored_database.write_bytes(b"old database")
    restored_storage.mkdir()
    stale = restored_storage / "stale-from-old-install.txt"
    stale.write_text("must disappear", encoding="utf-8")

    restore_sqlite(bundle, restored_database, restored_storage, force=True)

    assert not stale.exists()
    with sqlite3.connect(restored_database) as connection:
        connection.execute("SELECT 1").fetchone()


def test_failed_verification_leaves_existing_targets_untouched(tmp_path: Path):
    bundle = tmp_path / "invalid-backup.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("database.sqlite", b"replacement")
        archive.writestr("storage/new.txt", b"replacement")

    database = tmp_path / "target" / "db.sqlite"
    storage = tmp_path / "target" / "storage"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"original-db")
    storage.mkdir()
    existing = storage / "existing.txt"
    existing.write_bytes(b"original-storage")

    with pytest.raises(Exception):
        restore_sqlite(bundle, database, storage, force=True)

    assert database.read_bytes() == b"original-db"
    assert existing.read_bytes() == b"original-storage"


def test_storage_restore_is_available_for_postgres_bundles(tmp_path: Path):
    bundle = tmp_path / "postgres-backup.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("storage/tenant/document.pdf", b"document")
    target = tmp_path / "restored-storage"
    assert restore_storage(bundle, target) == 1
    assert (target / "tenant/document.pdf").read_bytes() == b"document"


def test_force_storage_restore_removes_files_not_in_backup(tmp_path: Path):
    bundle = tmp_path / "storage.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("storage/current.txt", b"current")
    target = tmp_path / "storage"
    target.mkdir()
    (target / "stale.txt").write_bytes(b"stale")

    assert restore_storage(bundle, target, force=True) == 1
    assert (target / "current.txt").read_bytes() == b"current"
    assert not (target / "stale.txt").exists()


def test_storage_restore_rejects_traversal_before_target_mutation(tmp_path: Path):
    bundle = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("storage/../escape.txt", b"bad")
    target = tmp_path / "storage"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_bytes(b"keep")

    with pytest.raises(RuntimeError, match="Unsafe storage restore path"):
        restore_storage(bundle, target, force=True)

    assert marker.read_bytes() == b"keep"
    assert not (tmp_path / "escape.txt").exists()


def test_pg_dump_url_normalizes_sqlalchemy_driver_scheme():
    assert _libpq_url("postgresql+psycopg://user:pass@db:5432/name") == "postgresql://user:pass@db:5432/name"
    assert _libpq_url("postgresql://user:pass@db/name") == "postgresql://user:pass@db/name"
