#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess  # nosec B404
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def verify_backup(bundle: Path) -> dict:
    bundle = bundle.resolve()
    if not bundle.is_file():
        raise FileNotFoundError(bundle)
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("Backup contains duplicate paths")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"Unsafe backup path: {name}")
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Backup manifest is missing or invalid") from exc
        if manifest.get("format") != "thistinti-backup-v1":
            raise RuntimeError("Unsupported backup format")
        declared_paths = {entry["path"] for entry in manifest.get("entries", [])}
        actual_paths = set(names) - {"manifest.json"}
        if declared_paths != actual_paths:
            raise RuntimeError("Backup entries do not match the manifest")
        for entry in manifest["entries"]:
            data = archive.read(entry["path"])
            if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"Backup entry failed integrity verification: {entry['path']}")

        database_engine = manifest.get("database_engine")
        with tempfile.TemporaryDirectory(prefix="thistinti-backup-verify-") as temporary:
            root = Path(temporary)
            if database_engine == "sqlite":
                database = root / "database.sqlite"
                database.write_bytes(archive.read("database.sqlite"))
                connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
                try:
                    result = connection.execute("PRAGMA integrity_check").fetchone()
                finally:
                    connection.close()
                if not result or result[0] != "ok":
                    raise RuntimeError(f"SQLite integrity check failed: {result}")
            elif database_engine == "postgresql":
                executable = shutil.which("pg_restore")
                if executable:
                    dump = root / "database.dump"
                    dump.write_bytes(archive.read("database.dump"))
                    subprocess.run(  # nosec B603
                        [executable, "--list", str(dump)], check=True, timeout=120, capture_output=True
                    )
            else:
                raise RuntimeError("Unknown database engine in backup")
    return {
        "valid": True,
        "format": manifest["format"],
        "database_engine": manifest["database_engine"],
        "release_version": manifest.get("release_version"),
        "entries": len(manifest["entries"]),
        "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a ThisTinti backup without modifying the live system")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_backup(args.bundle), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
