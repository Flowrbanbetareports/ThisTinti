#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_artifact import build_distribution_identity


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the identity embedded in a Windows portable archive.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--workflow-run", type=int, required=True)
    parser.add_argument("--workflow-run-number", type=int, required=True)
    parser.add_argument("--artifact-name", required=True)
    args = parser.parse_args()

    identity = build_distribution_identity(
        version=args.version,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        workflow_run=args.workflow_run,
        workflow_run_number=args.workflow_run_number,
        artifact_name=args.artifact_name,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
