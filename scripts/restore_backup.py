#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_backup import verify_backup  # noqa: E402


def _safe_storage_members(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    seen: set[str] = set()
    for info in archive.infolist():
        normalized_name = info.filename.replace("\\", "/")
        if not normalized_name.startswith("storage/") or normalized_name.endswith("/"):
            continue
        relative = PurePosixPath(normalized_name).relative_to("storage")
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"Unsafe storage restore path: {info.filename}")
        key = "/".join(relative.parts)
        if key in seen:
            raise RuntimeError(f"Duplicate storage restore path: {info.filename}")
        seen.add(key)
        members.append((info, relative))
    return members


def _stage_storage(bundle: Path, stage_target: Path) -> int:
    stage_target.mkdir(parents=True, exist_ok=False)
    restored = 0
    with zipfile.ZipFile(bundle) as archive:
        members = _safe_storage_members(archive)
        for info, relative in members:
            target = stage_target.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
            restored += 1
    return restored


def _target_nonempty(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        return any(path.iterdir())
    return True


def _backup_path(target: Path) -> Path:
    return target.parent / f".{target.name}.restore-backup-{uuid.uuid4().hex}"


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _replace_with_rollback(staged: Path, target: Path, *, force: bool) -> Path | None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if _target_nonempty(target) and not force:
        raise FileExistsError(f"Refusing to overwrite non-empty {target}; pass --force")
    backup: Path | None = None
    if target.exists():
        backup = _backup_path(target)
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    return backup


def restore_storage(bundle: Path, storage_target: Path, *, force: bool = False) -> int:
    storage_target = storage_target.resolve()
    storage_target.parent.mkdir(parents=True, exist_ok=True)
    if _target_nonempty(storage_target) and not force:
        raise FileExistsError(f"Refusing to overwrite non-empty {storage_target}; pass --force")

    with tempfile.TemporaryDirectory(prefix=".thistinti-storage-stage-", dir=storage_target.parent) as temporary:
        staged = Path(temporary) / "storage"
        restored = _stage_storage(bundle, staged)
        backup = _replace_with_rollback(staged, storage_target, force=force)
        if backup is not None:
            _remove_path(backup)
    return restored


def restore_sqlite(bundle: Path, database_target: Path, storage_target: Path, *, force: bool = False) -> None:
    result = verify_backup(bundle)
    if result["database_engine"] != "sqlite":
        raise RuntimeError("Backup is not a SQLite backup")

    database_target = database_target.resolve()
    storage_target = storage_target.resolve()
    database_target.parent.mkdir(parents=True, exist_ok=True)
    storage_target.parent.mkdir(parents=True, exist_ok=True)

    if database_target.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {database_target}; pass --force")
    if _target_nonempty(storage_target) and not force:
        raise FileExistsError(f"Refusing to overwrite non-empty {storage_target}; pass --force")

    with (
        tempfile.TemporaryDirectory(prefix=".thistinti-db-stage-", dir=database_target.parent) as db_temporary,
        tempfile.TemporaryDirectory(prefix=".thistinti-storage-stage-", dir=storage_target.parent) as storage_temporary,
        zipfile.ZipFile(bundle) as archive,
    ):
        staged_database = Path(db_temporary) / "database.sqlite"
        with archive.open("database.sqlite") as source, staged_database.open("wb") as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)

        staged_storage = Path(storage_temporary) / "storage"
        _stage_storage(bundle, staged_storage)

        db_backup: Path | None = None
        storage_backup: Path | None = None
        db_installed = False
        storage_installed = False
        try:
            db_backup = _replace_with_rollback(staged_database, database_target, force=force)
            db_installed = True
            storage_backup = _replace_with_rollback(staged_storage, storage_target, force=force)
            storage_installed = True
        except Exception:
            if storage_installed:
                _remove_path(storage_target)
            if storage_backup is not None and storage_backup.exists():
                os.replace(storage_backup, storage_target)
            if db_installed:
                _remove_path(database_target)
            if db_backup is not None and db_backup.exists():
                os.replace(db_backup, database_target)
            raise
        else:
            if db_backup is not None:
                _remove_path(db_backup)
            if storage_backup is not None:
                _remove_path(storage_backup)


def restore_postgres(
    bundle: Path,
    database_url: str,
    *,
    storage_target: Path | None = None,
    force_storage: bool = False,
    confirm: bool = False,
) -> None:
    result = verify_backup(bundle)
    if result["database_engine"] != "postgresql":
        raise RuntimeError("Backup is not a PostgreSQL dump")
    if not confirm:
        raise RuntimeError("PostgreSQL restore requires --confirm-restore")
    executable = shutil.which("pg_restore")
    if executable is None:
        raise RuntimeError("pg_restore is required")

    staged_storage_root: tempfile.TemporaryDirectory[str] | None = None
    staged_storage: Path | None = None
    if storage_target is not None:
        storage_target = storage_target.resolve()
        storage_target.parent.mkdir(parents=True, exist_ok=True)
        if _target_nonempty(storage_target) and not force_storage:
            raise FileExistsError(f"Refusing to overwrite non-empty {storage_target}; pass --force")
        staged_storage_root = tempfile.TemporaryDirectory(prefix=".thistinti-storage-stage-", dir=storage_target.parent)
        staged_storage = Path(staged_storage_root.name) / "storage"
        _stage_storage(bundle, staged_storage)

    try:
        with (
            zipfile.ZipFile(bundle) as archive,
            tempfile.TemporaryDirectory(prefix="thistinti-pg-restore-") as temporary,
        ):
            dump = Path(temporary) / "database.dump"
            with archive.open("database.dump") as source, dump.open("wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
            subprocess.run(  # nosec B603
                [
                    executable,
                    "--clean",
                    "--if-exists",
                    "--single-transaction",
                    "--no-owner",
                    "--no-privileges",
                    "--dbname",
                    database_url,
                    str(dump),
                ],
                check=True,
                timeout=1800,
                env=os.environ.copy(),
            )

        if storage_target is not None and staged_storage is not None:
            backup = _replace_with_rollback(staged_storage, storage_target, force=force_storage)
            if backup is not None:
                _remove_path(backup)
    finally:
        if staged_storage_root is not None:
            staged_storage_root.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a verified ThisTinti backup into an explicit target")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--sqlite-database", type=Path)
    parser.add_argument("--storage-dir", type=Path)
    parser.add_argument("--postgres-url")
    parser.add_argument("--postgres-url-file", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()
    postgres_url = args.postgres_url
    if args.postgres_url_file:
        if postgres_url:
            parser.error("Choose only one of --postgres-url and --postgres-url-file")
        postgres_url = args.postgres_url_file.read_text(encoding="utf-8").strip()
    if postgres_url:
        restore_postgres(
            args.bundle,
            postgres_url,
            storage_target=args.storage_dir,
            force_storage=args.force,
            confirm=args.confirm_restore,
        )
    elif args.sqlite_database and args.storage_dir:
        restore_sqlite(args.bundle, args.sqlite_database, args.storage_dir, force=args.force)
    else:
        parser.error("Choose --postgres-url or both --sqlite-database and --storage-dir")
    print("Restore completed and source backup verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
