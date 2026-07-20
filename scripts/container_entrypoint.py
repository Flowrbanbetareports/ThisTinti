#!/usr/bin/env python3
"""Read Docker secret files as root, then drop privileges before starting ThisTinti."""

from __future__ import annotations

import os
import pwd
import sys
from pathlib import Path

SECRET_PREFIX = "THISTINTI_"
SECRET_SUFFIX = "_FILE"
RUNTIME_USER = "thistinti"


def stage_secret_files(target_root: Path, *, uid: int, gid: int) -> dict[str, str]:
    """Copy configured secret files to an app-readable, process-private directory."""
    target_root.mkdir(parents=True, exist_ok=True)
    os.chmod(target_root, 0o700)
    os.chown(target_root, uid, gid)
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
    return rewritten


def drop_privileges_and_exec(argv: list[str]) -> None:
    if not argv:
        raise RuntimeError("Container entrypoint requires a command")
    if os.geteuid() == 0:
        account = pwd.getpwnam(RUNTIME_USER)
        os.umask(0o077)
        os.environ.update(stage_secret_files(Path("/tmp/thistinti-secrets"), uid=account.pw_uid, gid=account.pw_gid))
        os.initgroups(account.pw_name, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    os.execvpe(argv[0], argv, os.environ)


def main() -> int:
    drop_privileges_and_exec(sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
