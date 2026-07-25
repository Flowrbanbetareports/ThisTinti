#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REQUIRED_WORKFLOWS = {
    "ThisTinti CI and External Proof",
    "Beta Readiness",
    "Enterprise Self-Hosted Reference Proof",
    "Build Windows Free Download",
}


def github_json(url: str, token: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ThisTinti-release-gate",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:  # nosec B310
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("GitHub API returned a non-object response")
    return value


def validate_candidate_payloads(
    *,
    target_sha: str,
    windows_run_id: int,
    windows_run: dict[str, Any],
    artifacts: list[dict[str, Any]],
    workflow_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    failures: list[str] = []
    if windows_run.get("id") != windows_run_id:
        failures.append("Windows workflow run ID does not match")
    if windows_run.get("name") != "Build Windows Free Download":
        failures.append("Selected workflow is not the Windows release build")
    if windows_run.get("event") != "push" or windows_run.get("head_branch") != "main":
        failures.append("Windows release artifact must come from a push build on main")
    if windows_run.get("status") != "completed" or windows_run.get("conclusion") != "success":
        failures.append("Windows release build is not successfully completed")
    if windows_run.get("head_sha") != target_sha:
        failures.append("Windows release build does not belong to the target commit")

    run_number = windows_run.get("run_number")
    expected_name = f"ThisTinti-Windows-{windows_run_id}-{run_number}"
    matching = [
        artifact for artifact in artifacts if artifact.get("name") == expected_name and artifact.get("expired") is False
    ]
    if len(matching) != 1:
        failures.append(f"Expected one unexpired artifact named {expected_name}")

    successful = {
        run.get("name")
        for run in workflow_runs
        if run.get("head_sha") == target_sha and run.get("status") == "completed" and run.get("conclusion") == "success"
    }
    missing_workflows = sorted(REQUIRED_WORKFLOWS - successful)
    if missing_workflows:
        failures.append(f"Required workflows are not green for the target commit: {missing_workflows}")
    if failures:
        raise ValueError("; ".join(failures))
    artifact = matching[0]
    return {
        "target_sha": target_sha,
        "windows_run_id": windows_run_id,
        "windows_run_number": run_number,
        "artifact_id": artifact.get("id"),
        "artifact_name": expected_name,
        "artifact_digest": artifact.get("digest"),
        "required_workflows": sorted(REQUIRED_WORKFLOWS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Require green workflows and an exact-commit Windows artifact.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--windows-run-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 2
    if not REPOSITORY_PATTERN.fullmatch(args.repository):
        print("Invalid GitHub repository name", file=sys.stderr)
        return 2
    if not COMMIT_PATTERN.fullmatch(args.target_sha):
        print("Target SHA must be a full lowercase Git commit", file=sys.stderr)
        return 2

    base = f"https://api.github.com/repos/{args.repository}"
    try:
        windows_run = github_json(f"{base}/actions/runs/{args.windows_run_id}", token)
        artifacts_payload = github_json(
            f"{base}/actions/runs/{args.windows_run_id}/artifacts?{urlencode({'per_page': 100})}",
            token,
        )
        workflow_payload = github_json(
            f"{base}/actions/runs?{urlencode({'head_sha': args.target_sha, 'status': 'completed', 'per_page': 100})}",
            token,
        )
        result = validate_candidate_payloads(
            target_sha=args.target_sha,
            windows_run_id=args.windows_run_id,
            windows_run=windows_run,
            artifacts=artifacts_payload.get("artifacts", []),
            workflow_runs=workflow_payload.get("workflow_runs", []),
        )
    except (OSError, ValueError) as exc:
        print(f"Publication candidate verification failed: {exc}", file=sys.stderr)
        return 1

    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Publication candidate verified: {args.target_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
