from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.backup_system import _libpq_url, create_backup
from scripts.restore_backup import restore_sqlite
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


def test_storage_restore_is_available_for_postgres_bundles(tmp_path: Path):
    import zipfile

    from scripts.restore_backup import restore_storage

    bundle = tmp_path / "postgres-backup.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("storage/tenant/document.pdf", b"document")
    target = tmp_path / "restored-storage"
    assert restore_storage(bundle, target) == 1
    assert (target / "tenant/document.pdf").read_bytes() == b"document"


def test_pg_dump_url_normalizes_sqlalchemy_driver_scheme():
    assert (
        _libpq_url("postgresql+psycopg://user:pass@db:5432/name")
        == "postgresql://user:pass@db:5432/name"
    )
    assert _libpq_url("postgresql://user:pass@db/name") == "postgresql://user:pass@db/name"
