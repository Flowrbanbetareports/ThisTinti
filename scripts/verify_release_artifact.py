#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from release_artifact import (
    distributable_files,
    load_json,
    required_release_files,
    sha256_file,
    validate_portable_identity,
    validate_smoke_reports,
    validate_source_identity,
    verify_checksum_sidecar,
)


def verify_artifact(
    directory: Path,
    *,
    expected_version: str,
    expected_commit: str,
    expected_tree: str,
) -> list[str]:
    failures: list[str] = []
    try:
        validate_source_identity(expected_commit, expected_tree)
        metadata = load_json(directory / "release-provenance.json")
        if metadata.get("schema") != "thistinti.release-provenance.v1":
            failures.append("Unsupported or missing provenance schema")
        if metadata.get("version") != expected_version:
            failures.append("Provenance version does not match the requested release")
        source = metadata.get("source") if isinstance(metadata.get("source"), dict) else {}
        if source.get("commit") != expected_commit:
            failures.append("Artifact source commit does not match the requested commit")
        if source.get("tree") != expected_tree:
            failures.append("Artifact source tree does not match the requested tree")

        missing = [name for name in required_release_files(expected_version) if not (directory / name).is_file()]
        if missing:
            failures.append(f"Missing release files: {missing}")
        if failures:
            return failures

        for stem in (
            f"ThisTinti-Setup-{expected_version}-x64.exe",
            f"ThisTinti-Portable-{expected_version}-x64.zip",
            f"ThisTinti-{expected_version}-self-hosted-source.zip",
        ):
            verify_checksum_sidecar(directory / stem, directory / f"{stem}.sha256")
        build = metadata.get("build") if isinstance(metadata.get("build"), dict) else {}
        validate_portable_identity(
            directory / f"ThisTinti-Portable-{expected_version}-x64.zip",
            expected_version=expected_version,
            expected_commit=expected_commit,
            expected_tree=expected_tree,
            expected_workflow_run=build.get("run_id"),
            expected_workflow_run_number=build.get("run_number"),
            expected_artifact_name=build.get("artifact_name"),
        )
        verification = metadata.get("verification") if isinstance(metadata.get("verification"), dict) else {}
        if verification.get("portable_identity_verified") is not True:
            failures.append("Provenance does not confirm the portable distribution identity")
        validate_smoke_reports(directory)

        listed = metadata.get("files")
        if not isinstance(listed, list):
            failures.append("Provenance file inventory is missing")
            return failures
        inventory = {str(item.get("name")): item for item in listed if isinstance(item, dict) and item.get("name")}
        actual_files = distributable_files(directory)
        actual_names = {path.name for path in actual_files}
        if set(inventory) != actual_names:
            failures.append("Provenance inventory does not exactly match distributable files")
            return failures
        for path in actual_files:
            item = inventory[path.name]
            if item.get("size") != path.stat().st_size:
                failures.append(f"Size mismatch for {path.name}")
            if item.get("sha256") != sha256_file(path):
                failures.append(f"SHA-256 mismatch for {path.name}")
    except (OSError, ValueError) as exc:
        failures.append(str(exc))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Windows release artifact and its source identity.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    args = parser.parse_args()
    failures = verify_artifact(
        args.directory.resolve(),
        expected_version=args.expected_version,
        expected_commit=args.expected_commit,
        expected_tree=args.expected_tree,
    )
    if failures:
        print("Release artifact verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Release artifact verified for {args.expected_version} ({args.expected_commit}, tree {args.expected_tree})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
