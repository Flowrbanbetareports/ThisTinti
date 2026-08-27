from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_actions_workflows_do_not_push_repository_refs() -> None:
    violations: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if re.search(r"^\s*git\s+push\b", line):
                violations.append(f"{workflow.name}:{line_no}: {line.strip()}")
    assert violations == [], "Actions must not advance repository refs directly:\n" + "\n".join(violations)


def test_benchmark_workflows_are_read_only_and_artifact_backed() -> None:
    for name in ("apparel-pre-pilot-30.yml", "public-evidence-benchmark-30.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "contents: read" in text
        assert "contents: write" not in text
        assert "actions/upload-artifact@" in text


def test_windows_release_workflow_is_read_only_and_artifact_backed() -> None:
    text = (WORKFLOWS / "windows-release.yml").read_text(encoding="utf-8")
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "actions/upload-artifact@" in text
    assert "Record successful main build" not in text


def test_runtime_entrypoint_drops_root_before_application_exec() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "container_entrypoint.py").read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["python", "scripts/container_entrypoint.py"]' in dockerfile
    assert "if os.geteuid() == 0:" in entrypoint
    assert "os.setgid(account.pw_gid)" in entrypoint
    assert "os.setuid(account.pw_uid)" in entrypoint
    assert "os.execvpe(argv[0], argv, os.environ)" in entrypoint


def test_publish_workflow_keeps_release_evidence_out_of_main() -> None:
    text = (WORKFLOWS / "publish-public-preview.yml").read_text(encoding="utf-8")
    assert "Generate immutable publication evidence" in text
    assert "Upload publication evidence without mutating main" in text
    assert "git push origin main" not in text
    assert "git push origin HEAD:main" not in text
