#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.parsers import ParseError, parse_file  # noqa: E402
from app.version import RELEASE_VERSION  # noqa: E402

DEFAULT_MANIFEST = ROOT / "samples" / "dirty_public_corpus_22.json"
MAX_SOURCE_BYTES = 25 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Characterize the raw external dirty-public corpus."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def download(
    client: httpx.Client,
    source: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    started = time.perf_counter()
    response = client.get(source["url"])
    response.raise_for_status()
    payload = response.content
    if not payload:
        raise ValueError("empty response")
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    return payload, {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(payload),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "final_url": str(response.url),
    }


def evaluate_parse(parsed: Any, expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    document_type = expected.get("document_type")
    if document_type and parsed.document_type != document_type:
        failures.append(
            f"document_type expected {document_type!r}, "
            f"got {parsed.document_type!r}"
        )
    number = expected.get("number")
    if number and parsed.number != number:
        failures.append(f"number expected {number!r}, got {parsed.number!r}")
    minimum_lines = expected.get("minimum_lines")
    if minimum_lines is not None and len(parsed.lines) < int(minimum_lines):
        failures.append(
            f"minimum_lines expected >= {minimum_lines}, got {len(parsed.lines)}"
        )
    currency = expected.get("currency")
    if currency and parsed.currency != currency:
        failures.append(f"currency expected {currency!r}, got {parsed.currency!r}")
    if expected.get("number_present") and not parsed.number:
        failures.append("document number missing")
    return failures


def markdown(report: dict[str, Any]) -> str:
    rows: list[str] = []
    for item in report["cases"]:
        result = "PASS" if item["expectation_passed"] else "FAIL"
        rows.append(
            "| "
            f"{item['id']} | {item['expectation_mode']} | "
            f"{item['parse']['status']} | {item['observed_sha256'][:12]} | "
            f"{result} |"
        )

    failures = [
        item
        for item in report["cases"]
        if item["expectation_mode"] != "characterize"
        and not item["expectation_passed"]
    ]
    failure_lines = (
        "\n".join(
            f"- `{item['id']}`: "
            + "; ".join(
                item["expectation_failures"] or ["source assertion mismatch"]
            )
            for item in failures
        )
        or "- none"
    )

    metrics = report["metrics"]
    gate = "PASS" if metrics["gate_passed"] else "FAIL"
    frozen = str(report["manifest"]["frozen"]).lower()
    rows_text = "\n".join(rows)
    return f"""# Dirty Public Corpus 22 — characterization result

Generated: `{report['generated_at']}`  
Engine: `{report['product']['engine_version']}`  
Manifest frozen: **{frozen}**

## What this is

A raw external-document characterization suite. Files are downloaded as published and are not normalized into ThisTinti's preferred JSON schema before parsing. It is not a real company pilot and it is not an accuracy claim.

## Summary

- cases: **{metrics['case_count']}**
- source-assertion cases: **{metrics['assertion_case_count']}**
- source-assertion passes: **{metrics['assertion_passes']}**
- source-assertion failures: **{metrics['assertion_failures']}**
- characterization-only cases: **{metrics['characterization_case_count']}**
- download failures: **{metrics['download_failures']}**
- unhandled exceptions: **{metrics['unhandled_exceptions']}**
- parsed: **{metrics['parse_status_counts'].get('parsed', 0)}**
- structured rejections: **{metrics['parse_status_counts'].get('parse_error', 0)}**
- gate: **{gate}**

| Case | Mode | Parser result | SHA-256 | Expectation |
|---|---|---|---|---|
{rows_text}

## Source-assertion failures

{failure_lines}

## Governance boundary

A PASS here proves only the frozen source assertions and crash-free handling encoded for these raw public/external files. Characterization-only packets are not correctness passes. This report does not prove performance on arbitrary company folders or a controlled authorized pilot.
"""


def parsed_summary(parsed: Any) -> dict[str, Any]:
    return {
        "status": "parsed",
        "document_type": parsed.document_type,
        "number": parsed.number,
        "document_date": (
            None if parsed.document_date is None else str(parsed.document_date)
        ),
        "currency": parsed.currency,
        "supplier_name": parsed.supplier_name,
        "line_count": len(parsed.lines),
        "confidence": parsed.confidence,
        "message": parsed.message,
        "metadata": {
            "extraction_method": parsed.metadata.get("extraction_method"),
            "pages": parsed.metadata.get("pages"),
            "profile": parsed.metadata.get("profile"),
        },
    }


def run_case(
    client: httpx.Client,
    source: dict[str, Any],
    workdir: Path,
) -> dict[str, Any]:
    expected = source.get("expected") or {}
    outcome = expected.get("outcome")
    result: dict[str, Any] = {
        "id": source["id"],
        "category": source["category"],
        "publisher": source["publisher"],
        "source_url": source["url"],
        "source_commit": source.get("source_commit"),
        "github_blob_sha": source.get("github_blob_sha"),
        "filename": source["filename"],
        "expectation_mode": outcome,
        "source_truth": expected.get("source_truth"),
        "standards_conformance": expected.get("standards_conformance"),
        "observed_sha256": "",
        "download": {"status": "pending"},
        "parse": {"status": "pending"},
        "expectation_passed": False,
        "expectation_failures": [],
    }

    try:
        payload, download_metadata = download(client, source)
    except (httpx.HTTPError, ValueError) as exc:
        result["download"] = {"status": "failed", "error": str(exc)}
        result["parse"] = {"status": "not_run"}
        result["expectation_failures"] = [f"download failed: {exc}"]
        return result

    result["observed_sha256"] = sha256_bytes(payload)
    result["download"] = {"status": "downloaded", **download_metadata}
    source_path = workdir / source["filename"]
    source_path.write_bytes(payload)

    parsed = None
    parse_error: ParseError | None = None
    try:
        parsed = parse_file(
            source_path,
            source["filename"],
            source.get("content_type"),
            source.get("overrides") or {},
        )
        result["parse"] = parsed_summary(parsed)
    except ParseError as exc:
        parse_error = exc
        result["parse"] = {
            "status": "parse_error",
            "code": exc.code,
            "message": str(exc),
            "line": exc.line,
            "field": exc.field,
            "reason": exc.reason,
        }
    except Exception as exc:  # noqa: BLE001
        result["parse"] = {
            "status": "unhandled_exception",
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }
        result["expectation_failures"].append(
            f"unhandled parser exception: {type(exc).__name__}: {exc}"
        )
        return result

    if outcome == "parse":
        if parse_error is not None:
            result["expectation_failures"].append(
                f"expected parse, got ParseError: {parse_error}"
            )
        else:
            result["expectation_failures"].extend(
                evaluate_parse(parsed, expected)
            )
    elif outcome == "safe_rejection":
        if parse_error is None:
            result["expectation_failures"].append(
                "expected structured ParseError rejection, but document parsed"
            )
    elif outcome == "characterize":
        pass
    else:
        result["expectation_failures"].append(
            f"unknown expected outcome: {outcome!r}"
        )

    result["expectation_passed"] = not result["expectation_failures"]
    return result


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    sources = manifest.get("sources") or []
    if len(sources) != 22:
        raise SystemExit(
            f"Dirty Public Corpus v1 must contain exactly 22 cases, got {len(sources)}"
        )

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(
        prefix="thistinti-dirty-public-"
    ) as temp_dir:
        workdir = Path(temp_dir)
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),
            headers={
                "User-Agent": "ThisTinti-dirty-public-corpus/0.2"
            },
        ) as client:
            cases = [run_case(client, source, workdir) for source in sources]

    parse_status_counts = Counter(item["parse"]["status"] for item in cases)
    download_failures = sum(
        item["download"]["status"] != "downloaded" for item in cases
    )
    unhandled = parse_status_counts.get("unhandled_exception", 0)
    assertion_cases = [
        item for item in cases if item["expectation_mode"] != "characterize"
    ]
    assertion_failures = sum(
        not item["expectation_passed"] for item in assertion_cases
    )
    assertion_passes = len(assertion_cases) - assertion_failures
    characterization_cases = [
        item for item in cases if item["expectation_mode"] == "characterize"
    ]

    frozen = bool(manifest.get("frozen"))
    reproducible = download_failures == 0 and unhandled == 0
    gate_passed = reproducible and (not frozen or assertion_failures == 0)

    report = {
        "schema": "thistinti.dirty-public-corpus-result.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product": {
            "name": "ThisTinti",
            "engine_version": RELEASE_VERSION,
        },
        "manifest": {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "frozen": frozen,
            "evidence_level": manifest.get("evidence_level"),
            "real_company_pilot": False,
        },
        "metrics": {
            "case_count": len(cases),
            "assertion_case_count": len(assertion_cases),
            "assertion_passes": assertion_passes,
            "assertion_failures": assertion_failures,
            "characterization_case_count": len(characterization_cases),
            "download_failures": download_failures,
            "unhandled_exceptions": unhandled,
            "parse_status_counts": dict(parse_status_counts),
            "gate_passed": gate_passed,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
        "cases": cases,
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    for item in cases:
        if (
            item["expectation_mode"] != "characterize"
            and not item["expectation_passed"]
        ):
            failures = "; ".join(item["expectation_failures"])
            print(f"ASSERTION_FAIL {item['id']}: {failures}")
        if item["expectation_mode"] == "characterize":
            parsed = item["parse"]
            print(
                "CHARACTERIZE "
                f"{item['id']} status={parsed['status']} "
                f"type={parsed.get('document_type')} "
                f"number={parsed.get('number')} "
                f"lines={parsed.get('line_count')}"
            )

    if not reproducible:
        return 2
    if frozen and not gate_passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
