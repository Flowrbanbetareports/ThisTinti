from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from app.local_runtime import (
    configure_local_environment,
    create_pre_migration_backup,
    default_data_root,
    ensure_local_layout,
    sqlite_url,
)


def test_default_data_root_can_be_overridden(monkeypatch, tmp_path: Path):
    target = tmp_path / "custom-home"
    monkeypatch.setenv("THISTINTI_HOME", str(target))
    assert default_data_root() == target.resolve()


def test_sqlite_url_uses_absolute_forward_slash_path(tmp_path: Path):
    url = sqlite_url(tmp_path / "database" / "thistinti.db")
    assert url.startswith("sqlite:///")
    assert "thistinti.db" in url
    assert "\\" not in url


def test_local_environment_is_private_and_persistent(monkeypatch, tmp_path: Path):
    for name in list(os.environ):
        if name.startswith("THISTINTI_") or name == "TESSDATA_PREFIX":
            monkeypatch.delenv(name, raising=False)
    paths = configure_local_environment(tmp_path, port=18765)
    first_secret = (paths["config"] / "secret.key").read_text(encoding="utf-8")
    assert len(first_secret) >= 32
    assert os.environ["THISTINTI_ENV"] == "local"
    assert os.environ["THISTINTI_LOCAL_EDITION"] == "true"
    assert os.environ["THISTINTI_ASYNC_INGESTION_ENABLED"] == "true"
    assert os.environ["THISTINTI_ALLOW_SYNCHRONOUS_INGESTION"] == "false"
    assert os.environ["THISTINTI_DATABASE_URL"] == sqlite_url(paths["database"])
    metadata = json.loads((paths["config"] / "local-edition.json").read_text(encoding="utf-8"))
    assert metadata["telemetry"] is False
    assert metadata["cloud_required"] is False

    configure_local_environment(tmp_path, port=18765)
    assert (paths["config"] / "secret.key").read_text(encoding="utf-8") == first_secret


def test_pre_migration_backup_preserves_database_files(tmp_path: Path):
    paths = ensure_local_layout(tmp_path)
    paths["database"].write_bytes(b"sqlite-data")
    Path(str(paths["database"]) + "-wal").write_bytes(b"wal-data")
    backup = create_pre_migration_backup(tmp_path)
    assert backup is not None and backup.exists()
    with zipfile.ZipFile(backup) as archive:
        assert archive.read("database/thistinti.db") == b"sqlite-data"
        assert archive.read("database/thistinti.db-wal") == b"wal-data"


def test_resource_root_uses_frozen_bundle(monkeypatch, tmp_path: Path):
    from app import local_runtime

    monkeypatch.setattr(local_runtime.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert local_runtime.resource_root() == tmp_path


def test_invalid_persisted_secret_is_rejected(tmp_path: Path):
    from app.local_runtime import ensure_local_secret

    config = tmp_path / "config"
    config.mkdir()
    (config / "secret.key").write_text("short", encoding="utf-8")
    try:
        ensure_local_secret(config)
    except RuntimeError as exc:
        assert "segreto locale" in str(exc)
    else:
        raise AssertionError("An invalid local secret must be rejected")


def test_bundled_ocr_directory_is_added_to_environment(monkeypatch, tmp_path: Path):
    from app import local_runtime

    root = tmp_path / "bundle"
    tesseract = root / "ocr" / "tesseract"
    tesseract.mkdir(parents=True)
    monkeypatch.setattr(local_runtime, "resource_root", lambda: root)
    monkeypatch.setenv("PATH", "existing-path")
    configure_local_environment(tmp_path / "home", port=18766)
    assert os.environ["THISTINTI_TESSERACT_DIR"] == str(tesseract)
    assert os.environ["TESSDATA_PREFIX"] == str(tesseract / "tessdata")
    assert os.environ["PATH"].startswith(str(tesseract))


def test_copy_source_snapshot(monkeypatch, tmp_path: Path):
    from app import local_runtime

    root = tmp_path / "bundle"
    source = root / "source"
    source.mkdir(parents=True)
    (source / "README.md").write_text("source", encoding="utf-8")
    monkeypatch.setattr(local_runtime, "resource_root", lambda: root)
    destination = tmp_path / "export"
    local_runtime.copy_source_snapshot(destination)
    assert (destination / "ThisTinti-source" / "README.md").read_text(encoding="utf-8") == "source"


def test_full_backup_uses_consistent_sqlite_copy_and_excludes_secret(tmp_path: Path):
    import sqlite3

    from app.local_runtime import create_full_local_backup

    paths = ensure_local_layout(tmp_path)
    with sqlite3.connect(paths["database"]) as connection:
        connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO example (value) VALUES ('ok')")
        connection.commit()
    upload = paths["uploads"] / "document.txt"
    upload.write_text("content", encoding="utf-8")
    (paths["config"] / "secret.key").write_text("do-not-export", encoding="utf-8")

    backup = create_full_local_backup(tmp_path)
    with zipfile.ZipFile(backup) as archive:
        names = set(archive.namelist())
        assert "database/thistinti.db" in names
        assert "data/uploads/document.txt" in names
        assert "manifest.json" in names
        assert not any("secret" in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["configuration_scope"] == "data-only"
