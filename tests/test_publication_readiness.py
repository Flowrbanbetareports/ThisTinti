from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_publication_readiness_gate_passes():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/check_publication_readiness.py"],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_launch_documents_are_linked_from_readme():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for name in (
        "PUBLIC_LAUNCH_CHECKLIST.md",
        "NAME_AND_DOMAIN_CLEARANCE.md",
        "USER_GUIDE_SIMPLE.md",
        "PILOT_KIT.md",
        "LICENSE_REVIEW.md",
    ):
        assert name in readme
