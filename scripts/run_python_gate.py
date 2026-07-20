#!/usr/bin/env python3
from __future__ import annotations

import os
import runpy
import sys
import traceback
from pathlib import Path


def normalize_exit_code(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    print(value, file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in {"path", "module"}:
        print("usage: run_python_gate.py {path|module} TARGET [ARG ...]", file=sys.stderr)
        return 2
    mode = sys.argv[1]
    target = sys.argv[2]
    arguments = sys.argv[3:]
    sys.argv = [target, *arguments]
    try:
        if mode == "path":
            path = Path(target)
            if not path.is_absolute():
                path = Path.cwd() / path
            runpy.run_path(str(path), run_name="__main__")
        else:
            runpy.run_module(target, run_name="__main__", alter_sys=True)
    except SystemExit as exc:
        return normalize_exit_code(exc.code)
    except BaseException:  # noqa: BLE001 - preserve CLI traceback and deterministic exit
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    status = main()
    # This process exists solely to run one CLI gate. Some third-party packages
    # leave interpreter-cleanup threads alive after their CLI has completed.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)
