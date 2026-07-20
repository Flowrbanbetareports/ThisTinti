#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_backup import verify_backup  # noqa: E402


def restore_storage(bundle: Path, storage_target: Path, *, force: bool = False) -> int:
    storage_target = storage_target.resolve()
    if storage_target.exists() and any(storage_target.iterdir()) and not force:
        raise FileExistsError(f"Refusing to overwrite non-empty {storage_target}; pass --force")
    storage_target.mkdir(parents=True, exist_ok=True)
    restored = 0
    with zipfile.ZipFile(bundle) as archive:
        for name in archive.namelist():
            if not name.startswith("storage/") or name.endswith("/"):
                continue
            relative = Path(name).relative_to("storage")
            target = (storage_target / relative).resolve()
            if storage_target not in target.parents:
                raise RuntimeError(f"Unsafe storage restore path: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            restored += 1
    return restored


def restore_sqlite(bundle: Path, database_target: Path, storage_target: Path, *, force: bool = False) -> None:
    verify_backup(bundle)
    database_target = database_target.resolve()
    if database_target.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite {database_target}; pass --force")
    database_target.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(bundle) as archive, tempfile.TemporaryDirectory(prefix="thistinti-restore-") as temporary:
        staged_database = Path(temporary) / "database.sqlite"
        staged_database.write_bytes(archive.read("database.sqlite"))
        os.replace(staged_database, database_target)
    restore_storage(bundle, storage_target, force=force)


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
    with zipfile.ZipFile(bundle) as archive, tempfile.TemporaryDirectory(prefix="thistinti-pg-restore-") as temporary:
        dump = Path(temporary) / "database.dump"
        dump.write_bytes(archive.read("database.dump"))
        subprocess.run(  # nosec B603
            [
                executable,
                "--clean",
                "--if-exists",
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
    if storage_target is not None:
        restore_storage(bundle, storage_target, force=force_storage)


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
