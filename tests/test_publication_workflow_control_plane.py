from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-public-preview.yml"


def test_publication_recorder_runs_from_current_main_after_exact_source_gates() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    verify_source = workflow.index("make verify")
    verify_artifact = workflow.index("python scripts/verify_release_artifact.py")
    checkout_control_plane = workflow.index("git checkout main")
    run_recorder = workflow.index("python scripts/record_github_publication.py")

    assert verify_source < verify_artifact < checkout_control_plane < run_recorder
    assert "git pull --ff-only origin main" in workflow
    assert 'test "$(python -c \'from app.version import RELEASE_VERSION; print(RELEASE_VERSION)\')" = "$VERSION"' in workflow
