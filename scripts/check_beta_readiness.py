#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

INTERNAL_REQUIRED_FILES = (
    "docs/BETA_READINESS_STATUS.md",
    "docs/BETA_EXTERNAL_REVIEW_PACKET.md",
    "docs/ACCESSIBILITY_CONFORMANCE_PLAN.md",
    "docs/PERFORMANCE_AND_SLO.md",
    "docs/CODE_SIGNING_RUNBOOK.md",
    "docs/PILOT_KIT.md",
    "docs/PILOT_DATASET_SPEC.md",
    "docs/VALIDATION_PROTOCOL.md",
    "docs/PRODUCTION_READINESS.md",
    "docs/SECURE_DEVELOPMENT_BASELINE.md",
    "docs/THREAT_MODEL.md",
    "docs/evidence/beta/external-gates.json",
    "docs/sbom.cdx.json",
    "scripts/static_accessibility_audit.py",
    "scripts/beta_load_probe.py",
    "scripts/validate_pilot_dataset.py",
    ".github/workflows/beta-readiness.yml",
    ".github/workflows/windows-release.yml",
)

WORKFLOW_FILES = (
    ".github/workflows/ci.yml",
    ".github/workflows/enterprise-self-hosted.yml",
    ".github/workflows/lock-preview.yml",
    ".github/workflows/pages.yml",
    ".github/workflows/windows-release.yml",
    ".github/workflows/beta-readiness.yml",
)

EXTERNAL_GATES = (
    "real_pilot_30_scenarios",
    "independent_security_review",
    "legal_privacy_trademark_review",
    "wcag_2_2_aa_manual_review",
    "production_environment_load_restore",
    "windows_code_signing",
)


def read_version() -> str:
    text = (ROOT / "app/version.py").read_text(encoding="utf-8")
    match = re.search(r'RELEASE_VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        raise ValueError("RELEASE_VERSION not found")
    return match.group(1)


def check_workflow_pins() -> list[str]:
    failures: list[str] = []
    mutable_action = re.compile(r"^\s*-?\s*uses:\s*[^#\s]+@(v\d+|main|master)\s*(?:#.*)?$", re.MULTILINE)
    for relative in WORKFLOW_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        for match in mutable_action.finditer(path.read_text(encoding="utf-8")):
            failures.append(f"Mutable GitHub Action reference in {relative}: {match.group(0).strip()}")
    return failures


def load_external_gates() -> tuple[dict[str, Any], list[str]]:
    path = ROOT / "docs/evidence/beta/external-gates.json"
    failures: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"Cannot read external gate registry: {exc}"]
    gates = raw.get("gates")
    if not isinstance(gates, dict):
        return {}, ["External gate registry has no gates object"]
    for name in EXTERNAL_GATES:
        entry = gates.get(name)
        if not isinstance(entry, dict):
            failures.append(f"External gate missing: {name}")
            continue
        if not isinstance(entry.get("passed"), bool):
            failures.append(f"External gate passed value must be boolean: {name}")
        if entry.get("passed") and not entry.get("evidence"):
            failures.append(f"External gate marked passed without evidence: {name}")
    return raw, failures


def build_report(*, require_external: bool) -> dict[str, Any]:
    internal_failures: list[str] = []
    for relative in INTERNAL_REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size < 80:
            internal_failures.append(f"Missing or empty internal beta file: {relative}")

    try:
        version = read_version()
    except ValueError as exc:
        version = ""
        internal_failures.append(str(exc))

    if version and not re.fullmatch(r"3\.4\.0-alpha\.6-rc\.\d+", version):
        internal_failures.append(f"Candidate version is not an Alpha.6 release candidate: {version}")

    for relative in ("pyproject.toml", "installer/windows/ThisTinti.iss", "README.md", "RELEASE_NOTES.md"):
        path = ROOT / relative
        if not path.is_file():
            internal_failures.append(f"Version carrier missing: {relative}")
            continue
        if version and version not in path.read_text(encoding="utf-8"):
            internal_failures.append(f"Version {version} missing from {relative}")

    internal_failures.extend(check_workflow_pins())

    required_markers = {
        "app/schemas.py": ("authorized_use_confirmed", "anonymization_confirmed", "reviewer_refs"),
        "app/services/validation_reporting.py": ("redacted", "validation_report"),
        "scripts/validate_pilot_dataset.py": ("ready_for_controlled_pilot", "sensitive-key"),
        ".github/workflows/windows-release.yml": ("attest-build-provenance@",),
    }
    for relative, markers in required_markers.items():
        path = ROOT / relative
        if not path.is_file():
            internal_failures.append(f"Required implementation file missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                internal_failures.append(f"Required beta marker missing from {relative}: {marker}")

    external_registry, registry_failures = load_external_gates()
    internal_failures.extend(registry_failures)
    gates = external_registry.get("gates", {}) if isinstance(external_registry, dict) else {}
    external_open = [name for name in EXTERNAL_GATES if not bool(gates.get(name, {}).get("passed"))]

    internal_passed = not internal_failures
    external_passed = not external_open
    return {
        "schema": "thistinti.beta-readiness.v1",
        "candidate_version": version,
        "internal": {
            "passed": internal_passed,
            "failures": internal_failures,
        },
        "external": {
            "passed": external_passed,
            "open_gates": external_open,
            "registry": "docs/evidence/beta/external-gates.json",
        },
        "technical_beta_candidate": internal_passed,
        "validated_beta": internal_passed and external_passed,
        "required_mode_passed": internal_passed and (external_passed or not require_external),
        "limitations": [
            "Internal automation cannot create authorised real-world pilot evidence.",
            "Internal automation cannot replace independent legal, privacy, accessibility or security review.",
            "Code signing requires an externally controlled certificate and private key.",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate internal and external ThisTinti beta gates.")
    parser.add_argument("--require-external", action="store_true", help="Fail unless every external gate is evidenced")
    parser.add_argument("--report", type=Path, help="Write a JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(require_external=args.require_external)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if not report["required_mode_passed"]:
        print("Beta readiness gate failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
