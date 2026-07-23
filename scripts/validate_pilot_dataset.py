#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from app.schemas import ValidationDatasetPayload  # noqa: E402

SENSITIVE_KEY_FRAGMENTS = {
    "address",
    "bank",
    "bic",
    "email",
    "fiscal",
    "iban",
    "mail",
    "phone",
    "tax_code",
    "telephone",
}
SENSITIVE_VALUE_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE),
    "italian_tax_id": re.compile(r"\b(?:IT\d{11}|[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])\b", re.IGNORECASE),
}


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}"
            if isinstance(item, str):
                yield child, key_text, item
            yield from _walk(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def inspect_dataset(raw: dict[str, Any], payload: ValidationDatasetPayload, digest: str) -> dict[str, Any]:
    document_types: Counter[str] = Counter()
    mime_types: Counter[str] = Counter()
    expected_case_types: Counter[str] = Counter()
    filenames: Counter[str] = Counter()
    warnings: list[dict[str, str]] = []

    for scenario in payload.scenarios:
        for document in scenario.documents:
            filenames[document.filename] += 1
            mime_types[document.mime_type] += 1
            document_type = str(document.content.get("document_type") or "unknown")
            document_types[document_type] += 1
        for expected in scenario.expected:
            expected_case_types[expected.case_type] += 1

    for path, key, value in _walk(raw):
        normalized_key = key.casefold().replace("-", "_")
        if any(fragment in normalized_key for fragment in SENSITIVE_KEY_FRAGMENTS) and value.strip():
            warnings.append({"code": "sensitive-key", "path": path, "message": f"Review field '{key}'"})
        for name, pattern in SENSITIVE_VALUE_PATTERNS.items():
            if pattern.search(value):
                warnings.append({"code": name, "path": path, "message": f"Possible {name} value"})

    duplicate_filenames = sorted(name for name, count in filenames.items() if count > 1)
    if duplicate_filenames:
        warnings.append(
            {
                "code": "duplicate-filenames",
                "path": "$.scenarios",
                "message": f"Repeated filenames: {', '.join(duplicate_filenames[:10])}",
            }
        )

    evidence = payload.evidence.model_dump(mode="json") if payload.evidence else None
    return {
        "schema": "thistinti.pilot-dataset-inspection.v1",
        "sha256": digest,
        "name": payload.name,
        "version": payload.version,
        "evidence_level": payload.evidence_level,
        "scenario_count": len(payload.scenarios),
        "document_count": sum(document_types.values()),
        "expected_finding_count": sum(expected_case_types.values()),
        "document_types": dict(sorted(document_types.items())),
        "mime_types": dict(sorted(mime_types.items())),
        "expected_case_types": dict(sorted(expected_case_types.items())),
        "governance": {
            "evidence_metadata_present": evidence is not None,
            "authorized_use_confirmed": bool(evidence and evidence.get("authorized_use_confirmed")),
            "anonymization_confirmed": bool(evidence and evidence.get("anonymization_confirmed")),
            "reviewer_count": len(set(evidence.get("reviewer_refs", []))) if evidence else 0,
            "ground_truth_method_documented": bool(evidence and evidence.get("ground_truth_method")),
            "scope_documented": bool(evidence and evidence.get("scope")),
        },
        "warnings": warnings,
        "ready_for_controlled_pilot": payload.evidence_level in {"anonymized_pilot", "production"}
        and len(payload.scenarios) >= 30
        and evidence is not None
        and bool(evidence.get("authorized_use_confirmed")),
    }


def validate_path(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    raw = json.loads(data.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Dataset root must be a JSON object")
    payload = ValidationDatasetPayload.model_validate(raw)
    return inspect_dataset(raw, payload, digest)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a ThisTinti Validation Lab dataset and inspect pilot governance metadata."
    )
    parser.add_argument("dataset", type=Path, help="Validation Lab dataset JSON")
    parser.add_argument("--report", type=Path, help="Write the inspection report as JSON")
    parser.add_argument("--fail-on-warning", action="store_true", help="Return a non-zero exit code when warnings exist")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = validate_path(args.dataset)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"Pilot dataset validation failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if args.fail_on_warning and report["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
