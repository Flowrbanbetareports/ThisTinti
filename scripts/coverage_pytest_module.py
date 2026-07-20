#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

import coverage
import pytest

ROOT = Path(__file__).resolve().parents[1]


class CoverageExitPlugin:
    def __init__(self, cov: coverage.Coverage) -> None:
        self.cov = cov

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self.cov.stop()
        self.cov.save()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(int(exitstatus))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: coverage_pytest_module.py tests_or_module", file=sys.stderr)
        return 2
    test_path = Path(sys.argv[1])
    if not test_path.exists() or ROOT not in test_path.resolve().parents:
        print(f"Invalid test path: {test_path}", file=sys.stderr)
        return 2
    cov = coverage.Coverage(source=["app"], data_suffix=True)
    cov.start()
    return int(
        pytest.main(
            [
                "-q",
                "--maxfail=1",
                "--disable-warnings",
                str(test_path),
            ],
            plugins=[CoverageExitPlugin(cov)],
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
