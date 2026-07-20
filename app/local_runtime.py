from __future__ import annotations

import json
import os
import secrets
import sqlite3
import shutil
import stat
import sys
import zipfile
import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path

APP_DIR_NAME = "ThisTinti"
LOCAL_PORT = 8765


def resource_root() -> Path:
    """Return the immutable application resource directory."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[1]


def default_data_root() -> Path:
    override = os.getenv("THISTINTI_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME


def sqlite_url(path: Path) -> str:
    resolved = path.expanduser().resolve()
    return f"sqlite:///{resolved.as_posix()}"


def _write_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows ACLs are inherited from the user profile; chmod may be limited.
        pass


def ensure_local_layout(data_root: Path) -> dict[str, Path]:
    root = data_root.expanduser().resolve()
    paths = {
        "root": root,
        "database": root / "database" / "thistinti.db",
        "uploads": root / "data" / "uploads",
        "quarantine": root / "data" / "quarantine",
        "rejected": root / "data" / "rejected",
        "backups": root / "backups",
        "logs": root / "logs",
        "config": root / "config",
        "runtime": root / "runtime",
    }
    for key, path in paths.items():
        if key != "database":
            path.mkdir(parents=True, exist_ok=True)
    paths["database"].parent.mkdir(parents=True, exist_ok=True)
    return paths


def ensure_local_secret(config_dir: Path) -> str:
    secret_path = config_dir / "secret.key"
    if not secret_path.exists():
        _write_private_text(secret_path, secrets.token_urlsafe(64))
    secret = secret_path.read_text(encoding="utf-8").strip()
    if len(secret) < 32:
        raise RuntimeError("Il segreto locale non è valido. Eliminare config/secret.key e riavviare ThisTinti.")
    return secret


def configure_local_environment(data_root: Path, port: int = LOCAL_PORT) -> dict[str, Path]:
    """Configure a deterministic local-only runtime before importing the app."""
    paths = ensure_local_layout(data_root)
    secret = ensure_local_secret(paths["config"])

    critical = {
        "THISTINTI_ENV": "local",
        "THISTINTI_PROCESS_ROLE": "app",
        "THISTINTI_DATABASE_URL": sqlite_url(paths["database"]),
        "THISTINTI_STORAGE_DIR": str(paths["uploads"]),
        "THISTINTI_QUARANTINE_DIR": str(paths["quarantine"]),
        "THISTINTI_REJECTED_DIR": str(paths["rejected"]),
        "THISTINTI_SECRET_KEY": secret,
        "THISTINTI_AUTO_CREATE_SCHEMA": "false",
        "THISTINTI_ALLOW_REGISTRATION": "true",
        "THISTINTI_SECURE_COOKIES": "false",
        "THISTINTI_DATABASE_RATE_LIMITING": "false",
        "THISTINTI_ASYNC_INGESTION_ENABLED": "true",
        "THISTINTI_ALLOW_SYNCHRONOUS_INGESTION": "false",
        "THISTINTI_REQUIRE_MALWARE_SCANNER": "false",
        "THISTINTI_CORS_ORIGINS": f"http://127.0.0.1:{port},http://localhost:{port}",
        "THISTINTI_LOCAL_EDITION": "true",
        "THISTINTI_LEGAL_NOTICE_VERSION": "2026-07-20-v2",
    }
    for key, value in critical.items():
        os.environ[key] = value

    bundled_ocr = resource_root() / "ocr" / "tesseract"
    if bundled_ocr.exists():
        os.environ["THISTINTI_TESSERACT_DIR"] = str(bundled_ocr)
        os.environ["TESSDATA_PREFIX"] = str(bundled_ocr / "tessdata")
        os.environ["PATH"] = str(bundled_ocr) + os.pathsep + os.environ.get("PATH", "")

    metadata = {
        "edition": "local",
        "data_root": str(paths["root"]),
        "database": str(paths["database"]),
        "port": port,
        "telemetry": False,
        "cloud_required": False,
        "legal_notice_version": "2026-07-20-v2",
    }
    (paths["config"] / "local-edition.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return paths


def create_pre_migration_backup(data_root: Path, *, keep: int = 5) -> Path | None:
    paths = ensure_local_layout(data_root)
    database = paths["database"]
    if not database.exists() or database.stat().st_size == 0:
        return None
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = paths["backups"] / f"before-update-{timestamp}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for candidate in (database, Path(str(database) + "-wal"), Path(str(database) + "-shm")):
            if candidate.exists() and candidate.is_file():
                archive.write(candidate, arcname=f"database/{candidate.name}")
        edition_file = paths["config"] / "local-edition.json"
        if edition_file.exists():
            archive.write(edition_file, arcname="config/local-edition.json")
    backups = sorted(paths["backups"].glob("before-update-*.zip"), reverse=True)
    for obsolete in backups[max(1, keep) :]:
        obsolete.unlink(missing_ok=True)
    return target


def run_local_migrations(data_root: Path) -> Path | None:
    """Back up an existing SQLite database and apply the local schema version."""
    from .local_schema import local_schema_needs_upgrade, upgrade_local_schema

    backup = create_pre_migration_backup(data_root) if local_schema_needs_upgrade() else None
    upgrade_local_schema()
    return backup


def create_full_local_backup(data_root: Path, target: Path | None = None) -> Path:
    """Create a consistent, portable local backup without exposing the secret key."""
    paths = ensure_local_layout(data_root)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (target or (paths["backups"] / f"thistinti-full-{timestamp}.zip")).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="thistinti-local-backup-") as temporary:
        database_copy = Path(temporary) / "thistinti.db"
        if paths["database"].exists():
            with sqlite3.connect(paths["database"]) as source, sqlite3.connect(database_copy) as destination:
                source.backup(destination)
        else:
            database_copy.touch()

        manifest: dict[str, object] = {
            "format": "thistinti-local-backup-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "database": "database/thistinti.db",
            "files": [],
            "configuration_scope": "data-only",
        }
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.write(database_copy, arcname="database/thistinti.db")
            file_entries: list[dict[str, object]] = []
            for source_file in sorted(paths["uploads"].rglob("*")):
                if not source_file.is_file():
                    continue
                relative = source_file.relative_to(paths["uploads"])
                arcname = (Path("data/uploads") / relative).as_posix()
                digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
                archive.write(source_file, arcname=arcname)
                file_entries.append({"path": arcname, "sha256": digest, "size": source_file.stat().st_size})
            manifest["files"] = file_entries
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return output


def copy_source_snapshot(destination: Path) -> None:
    """Copy the source snapshot shipped beside the local build, when present."""
    source = resource_root() / "source"
    if not source.exists():
        raise FileNotFoundError("Il pacchetto non include il sorgente.")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination / "ThisTinti-source", dirs_exist_ok=True)
