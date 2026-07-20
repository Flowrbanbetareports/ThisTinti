#!/usr/bin/env python3
"""Read Docker secret files as root, then drop privileges before starting ThisTinti."""

from __future__ import annotations

import os
import pwd
import stat
import sys
import tempfile
from pathlib import Path

# Environment-variable naming fragments, not credentials.
SECRET_PREFIX = "THISTINTI_"  # nosec B105
SECRET_SUFFIX = "_FILE"  # nosec B105
RUNTIME_USER = "thistinti"
WRITABLE_DIRECTORIES_ENV = "THISTINTI_ENTRYPOINT_WRITABLE_DIRECTORIES"
ALLOWED_WRITABLE_DIRECTORIES = frozenset({"/backups"})


def stage_secret_files(target_root: Path, *, uid: int, gid: int) -> dict[str, str]:
    """Copy configured secret files to an app-readable, process-private directory."""
    target_root.mkdir(parents=True, exist_ok=True)
    os.chmod(target_root, 0o700)
    rewritten: dict[str, str] = {}
    for key, value in sorted(os.environ.items()):
        if not (key.startswith(SECRET_PREFIX) and key.endswith(SECRET_SUFFIX) and value):
            continue
        source = Path(value)
        if not source.is_file():
            continue
        target = target_root / key.lower()
        data = source.read_bytes()
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o400)
        try:
            os.write(descriptor, data)
            os.fchmod(descriptor, 0o400)
            os.fchown(descriptor, uid, gid)
        finally:
            os.close(descriptor)
        rewritten[key] = str(target)
    # Keep the directory root-owned while files are written, then transfer it as
    # the final step so the unprivileged process can traverse it after setuid().
    os.chown(target_root, uid, gid)
    return rewritten


def prepare_writable_directories(value: str, *, uid: int, gid: int) -> list[Path]:
    """Transfer explicitly allow-listed bind mounts to the runtime account."""
    prepared: list[Path] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if raw not in ALLOWED_WRITABLE_DIRECTORIES:
            raise RuntimeError(f"Writable directory is not allow-listed: {raw}")
        path = Path(raw)
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError(f"Writable path must be an existing directory, not a symlink: {raw}")
        os.chown(path, uid, gid)
        os.chmod(path, 0o700)
        prepared.append(path)
    return prepared


def drop_privileges_and_exec(argv: list[str]) -> None:
    if not argv:
        raise RuntimeError("Container entrypoint requires a command")
    if os.geteuid() == 0:
        account = pwd.getpwnam(RUNTIME_USER)
        os.umask(0o077)
        target_root = Path(tempfile.mkdtemp(prefix="thistinti-secrets-"))
        os.environ.update(stage_secret_files(target_root, uid=account.pw_uid, gid=account.pw_gid))
        prepare_writable_directories(
            os.getenv(WRITABLE_DIRECTORIES_ENV, ""),
            uid=account.pw_uid,
            gid=account.pw_gid,
        )
        os.initgroups(account.pw_name, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    # Intentional exec-style handoff: no shell is involved and argv is supplied by Compose.
    os.execvpe(argv[0], argv, os.environ)  # nosec B606


def main() -> int:
    drop_privileges_and_exec(sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
