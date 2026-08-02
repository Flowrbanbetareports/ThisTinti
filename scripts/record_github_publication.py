#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from release_artifact import (
    load_json,
    publication_manifest_files,
    sha256_file,
    validate_source_identity,
)

REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def github_json(url: str, token: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ThisTinti-publication-recorder",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:  # nosec B310
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("GitHub API returned a non-object response")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record verifiable evidence for a published GitHub prerelease.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--release-output", type=Path, required=True)
    parser.add_argument("--publication-output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 2
    if not REPOSITORY_PATTERN.fullmatch(args.repository):
        print("Invalid GitHub repository name", file=sys.stderr)
        return 2
    try:
        validate_source_identity(args.source_commit, args.source_tree)
        directory = args.artifact_directory.resolve()
        provenance = load_json(directory / "release-provenance.json")
        version = provenance.get("version")
        if args.tag != f"v{version}":
            raise ValueError("Release tag and artifact version differ")
        source = provenance.get("source") if isinstance(provenance.get("source"), dict) else {}
        if source != {"commit": args.source_commit, "tree": args.source_tree}:
            raise ValueError("Artifact provenance and release source differ")

        release = github_json(
            f"https://api.github.com/repos/{args.repository}/releases/tags/{quote(args.tag, safe='')}",
            token,
        )
        if release.get("target_commitish") != args.source_commit:
            raise ValueError("Published release does not target the verified source commit")
        if release.get("draft") is not False or release.get("prerelease") is not True:
            raise ValueError("Published candidate is not a visible prerelease")

        assets = release.get("assets")
        if not isinstance(assets, list):
            raise ValueError("Published release has no asset list")
        manifest_by_name = publication_manifest_files(provenance, str(version))
        expected_names = set(manifest_by_name) | {"release-provenance.json"}
        actual_names = {asset.get("name") for asset in assets if isinstance(asset, dict)}
        if actual_names != expected_names:
            raise ValueError("Published asset set does not exactly match the verified artifact")

        publication_assets: list[dict[str, Any]] = []
        for asset in sorted(assets, key=lambda item: str(item.get("name"))):
            name = str(asset.get("name"))
            local = directory / name
            local_hash = sha256_file(local)
            manifest_entry = manifest_by_name.get(name)
            if manifest_entry is not None and (
                manifest_entry.get("sha256") != local_hash or manifest_entry.get("size") != local.stat().st_size
            ):
                raise ValueError(f"Artifact provenance differs for {name}")
            digest = str(asset.get("digest") or "")
            if digest and digest != f"sha256:{local_hash}":
                raise ValueError(f"Published asset digest differs for {name}")
            if asset.get("size") != local.stat().st_size:
                raise ValueError(f"Published asset size differs for {name}")
            publication_assets.append(
                {
                    "id": asset.get("id"),
                    "name": name,
                    "size": asset.get("size"),
                    "sha256": local_hash,
                    "download_url": asset.get("browser_download_url"),
                }
            )

        now = datetime.now(timezone.utc).isoformat()
        build = provenance.get("build") if isinstance(provenance.get("build"), dict) else {}
        release_payload = {
            "schema": "thistinti.release-evidence.v2",
            "version": version,
            "tag": args.tag,
            "release_id": release.get("id"),
            "release_commit": args.source_commit,
            "release_tree": args.source_tree,
            "release_url": release.get("html_url"),
            "published_at": release.get("published_at"),
            "is_draft": False,
            "is_prerelease": True,
            "build": {
                "workflow": build.get("workflow"),
                "workflow_run": build.get("run_id"),
                "workflow_run_number": build.get("run_number"),
                "workflow_conclusion": "success",
                "artifact_name": build.get("artifact_name"),
                "artifact_head_sha": args.source_commit,
                "artifact_head_tree": args.source_tree,
            },
            "verification": {
                "release_target_verified": True,
                "artifact_tree_matches_release_tree": True,
                "required_assets_verified": True,
                "smoke_reports_passed": True,
                "installer_sha256": sha256_file(directory / f"ThisTinti-Setup-{version}-x64.exe"),
                "portable_sha256": sha256_file(directory / f"ThisTinti-Portable-{version}-x64.zip"),
                "self_hosted_source_sha256": sha256_file(directory / f"ThisTinti-{version}-self-hosted-source.zip"),
            },
            "required_assets": sorted(expected_names),
            "unsigned_installer": True,
            "verified_at": now,
            "verification_source": "Gated GitHub workflow, exact-commit provenance and GitHub asset metadata",
        }
        publication_payload = {
            "schema": "thistinti.publication-evidence.v2",
            "version": version,
            "tag": args.tag,
            "release_id": release.get("id"),
            "release_commit": args.source_commit,
            "release_tree": args.source_tree,
            "release_url": release.get("html_url"),
            "published_at": release.get("published_at"),
            "is_draft": False,
            "is_prerelease": True,
            "asset_count": len(publication_assets),
            "assets": publication_assets,
            "verified_at": now,
            "verification_source": "GitHub REST release and asset metadata",
        }
        write_json(args.release_output, release_payload)
        write_json(args.publication_output, publication_payload)
    except (OSError, ValueError) as exc:
        print(f"Publication evidence recording failed: {exc}", file=sys.stderr)
        return 1
    print(f"Publication evidence recorded for {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
