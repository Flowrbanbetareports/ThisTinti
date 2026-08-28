#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from procurement_pilot.common import REVIEW_MODES
from procurement_pilot.evaluation import evaluate
from procurement_pilot.freeze import freeze_workspace
from procurement_pilot.ground_truth import (
    check_ready,
    create_ground_truth_templates,
    seal_ground_truth,
)
from procurement_pilot.workspace import inventory_private_documents, prepare_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Protocollo pilot Procurement di ThisTinti")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("workspace", type=Path)
    prepare.add_argument("--pilot-id", required=True)
    prepare.add_argument("--organization-alias", required=True)
    prepare.add_argument("--calibration-count", type=int, default=8)
    prepare.add_argument("--blind-count", type=int, default=22)
    prepare.add_argument("--review-mode", choices=sorted(REVIEW_MODES), default="dual_independent")

    inventory = sub.add_parser("inventory-private")
    inventory.add_argument("workspace", type=Path)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("workspace", type=Path)
    freeze.add_argument("--software-commit", required=True)
    freeze.add_argument("--software-version", required=True)
    for name in [
        "practice-model",
        "rule-pack",
        "provenance-matrix",
        "company-profile",
        "ground-truth-protocol",
        "evaluation-protocol",
    ]:
        freeze.add_argument(f"--{name}", type=Path, required=True)
        freeze.add_argument(f"--{name}-version", required=True)
    for command in ["create-ground-truth-templates", "seal-ground-truth", "check-ready", "evaluate"]:
        sub.add_parser(command).add_argument("workspace", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            payload = prepare_workspace(
                args.workspace,
                args.pilot_id,
                args.organization_alias,
                args.calibration_count,
                args.blind_count,
                args.review_mode,
            )
        elif args.command == "inventory-private":
            payload = inventory_private_documents(args.workspace)
        elif args.command == "freeze":
            payload = freeze_workspace(
                args.workspace,
                software_commit=args.software_commit,
                software_version=args.software_version,
                practice_model=args.practice_model,
                practice_model_version=args.practice_model_version,
                rule_pack=args.rule_pack,
                rule_pack_version=args.rule_pack_version,
                provenance_matrix=args.provenance_matrix,
                provenance_matrix_version=args.provenance_matrix_version,
                company_profile=args.company_profile,
                company_profile_version=args.company_profile_version,
                ground_truth_protocol=args.ground_truth_protocol,
                ground_truth_protocol_version=args.ground_truth_protocol_version,
                evaluation_protocol=args.evaluation_protocol,
                evaluation_protocol_version=args.evaluation_protocol_version,
            )
        elif args.command == "create-ground-truth-templates":
            payload = create_ground_truth_templates(args.workspace)
        elif args.command == "seal-ground-truth":
            payload = seal_ground_truth(args.workspace)
        elif args.command == "check-ready":
            payload = check_ready(args.workspace)
        elif args.command == "evaluate":
            payload = evaluate(args.workspace)
        else:
            raise AssertionError(args.command)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
