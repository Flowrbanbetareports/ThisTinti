from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-public-preview.yml"


def test_publication_recorder_stays_on_exact_reviewed_source_after_gates() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    detach_target = workflow.index('git checkout --detach "$TARGET_SHA"')
    constrain_source = workflow.index('git merge-base --is-ancestor "$TARGET_SHA" origin/main')
    verify_source = workflow.index("make verify")
    verify_artifact = workflow.index("python scripts/verify_release_artifact.py")
    publish_release = workflow.index('gh release create "$TAG" dist/*')
    run_recorder = workflow.index("python scripts/record_github_publication.py")

    assert detach_target < constrain_source < verify_source < verify_artifact < publish_release < run_recorder
    assert 'test "$(git rev-parse HEAD)" = "$TARGET_SHA"' in workflow
    assert "git checkout main" not in workflow
    assert "git pull --ff-only origin main" not in workflow
    assert "git push origin main" not in workflow
    assert "git push origin HEAD:main" not in workflow
