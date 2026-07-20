#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def worker_process_running() -> bool:
    for command_line in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            arguments = command_line.read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
        if any(argument.endswith(b"scripts/run_worker.py") for argument in arguments):
            return True
    return False


def main() -> int:
    return 0 if worker_process_running() else 1


if __name__ == "__main__":
    raise SystemExit(main())
