#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess  # nosec B404
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.version import RELEASE_VERSION  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sqlite_path(database_url: str) -> Path:
    prefixes = ("sqlite:///", "sqlite+pysqlite:///")
    for prefix in prefixes:
        if database_url.startswith(prefix):
            return Path(database_url[len(prefix) :]).resolve()
    raise ValueError("Not a file-based SQLite URL")


def _libpq_url(database_url: str) -> str:
    """Convert SQLAlchemy PostgreSQL driver URLs to a URI accepted by pg_dump."""
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if database_url.startswith(prefix):
            return "postgresql://" + database_url[len(prefix) :]
    return database_url


def _snapshot_sqlite(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        target_connection = sqlite3.connect(target)
        try:
            source_connection.backup(target_connection)
            result = target_connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError(f"SQLite backup integrity check failed: {result}")
        finally:
            target_connection.close()
    finally:
        source_connection.close()


def _snapshot_postgres(database_url: str, target: Path) -> None:
    executable = shutil.which("pg_dump")
    if executable is None:
        raise RuntimeError("pg_dump is required for PostgreSQL backups")
    subprocess.run(  # nosec B603
        [
            executable,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(target),
            _libpq_url(database_url),
        ],
        check=True,
        timeout=1800,
        env=os.environ.copy(),
    )


def _safe_storage_files(storage_dir: Path) -> list[Path]:
    if not storage_dir.exists():
        return []
    root = storage_dir.resolve()
    files: list[Path] = []
    for path in sorted(storage_dir.rglob("*")):
        if path.is_symlink():
            continue
        if path.is_file():
            resolved = path.resolve()
            if root not in resolved.parents:
                raise RuntimeError(f"Storage path escapes root: {path}")
            files.append(resolved)
    return files


def create_backup(output_path: Path, *, include_storage: bool = True) -> dict:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    manifest: dict = {
        "format": "thistinti-backup-v1",
        "release_version": RELEASE_VERSION,
        "created_at": created_at,
        "database_engine": "postgresql" if settings.database_url.startswith("postgresql") else "sqlite",
        "entries": [],
        "storage_included": include_storage,
    }

    with tempfile.TemporaryDirectory(prefix="thistinti-backup-") as temporary:
        temp_root = Path(temporary)
        if manifest["database_engine"] == "sqlite":
            database_name = "database.sqlite"
            database_snapshot = temp_root / database_name
            _snapshot_sqlite(_sqlite_path(settings.database_url), database_snapshot)
        else:
            database_name = "database.dump"
            database_snapshot = temp_root / database_name
            _snapshot_postgres(settings.database_url, database_snapshot)

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            database_bytes = database_snapshot.read_bytes()
            archive.writestr(database_name, database_bytes)
            manifest["entries"].append(
                {"path": database_name, "size": len(database_bytes), "sha256": sha256_bytes(database_bytes)}
            )

            if include_storage:
                storage_root = settings.storage_dir.resolve()
                for source in _safe_storage_files(storage_root):
                    relative = source.relative_to(storage_root).as_posix()
                    archive_name = f"storage/{relative}"
                    data = source.read_bytes()
                    archive.writestr(archive_name, data)
                    manifest["entries"].append({"path": archive_name, "size": len(data), "sha256": sha256_bytes(data)})

            manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            archive.writestr("manifest.json", manifest_bytes)

    manifest["bundle_path"] = str(output_path)
    manifest["bundle_size"] = output_path.stat().st_size
    manifest["bundle_sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a consistent ThisTinti database and storage backup")
    parser.add_argument("output", type=Path)
    parser.add_argument("--database-only", action="store_true", help="Exclude uploaded source files")
    args = parser.parse_args()
    result = create_backup(args.output, include_storage=not args.database_only)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
