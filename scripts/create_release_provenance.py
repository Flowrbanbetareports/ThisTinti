#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Create provenance metadata for an exact Windows release artifact.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--workflow-run", type=int, required=True)
    parser.add_argument("--workflow-run-number", type=int, required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    args = parser.parse_args()

    directory = args.directory.resolve()
    validate_source_identity(args.source_commit, args.source_tree)
    baseline = load_json(args.baseline_manifest.resolve())
    missing = [name for name in required_release_files(args.version) if not (directory / name).is_file()]
    if missing:
        raise ValueError(f"Missing release files: {missing}")

    for stem in (
        f"ThisTinti-Setup-{args.version}-x64.exe",
        f"ThisTinti-Portable-{args.version}-x64.zip",
        f"ThisTinti-{args.version}-self-hosted-source.zip",
    ):
        verify_checksum_sidecar(directory / stem, directory / f"{stem}.sha256")
    validate_portable_identity(
        directory / f"ThisTinti-Portable-{args.version}-x64.zip",
        expected_version=args.version,
        expected_commit=args.source_commit,
        expected_tree=args.source_tree,
        expected_workflow_run=args.workflow_run,
        expected_workflow_run_number=args.workflow_run_number,
        expected_artifact_name=args.artifact_name,
    )
    validate_smoke_reports(directory)

    files = [
        {"name": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in distributable_files(directory)
    ]
    payload = {
        "schema": "thistinti.release-provenance.v1",
        "version": args.version,
        "source": {"commit": args.source_commit, "tree": args.source_tree},
        "build": {
            "workflow": "Build Windows Free Download",
            "run_id": args.workflow_run,
            "run_number": args.workflow_run_number,
            "artifact_name": args.artifact_name,
        },
        "upgrade_baseline": {
            "version": baseline.get("version"),
            "tag": baseline.get("tag"),
            "release_commit": baseline.get("release_commit"),
            "installer": baseline.get("installer"),
            "sha256": baseline.get("sha256"),
        },
        "verification": {
            "checksums_verified": True,
            "portable_identity_verified": True,
            "frozen_smoke_passed": True,
            "installed_smoke_passed": True,
            "installed_diagnostics_passed": True,
            "installer_lifecycle_passed": True,
        },
        "files": files,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output = directory / "release-provenance.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
