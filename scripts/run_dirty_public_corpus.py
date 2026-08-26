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
    parser = argparse.ArgumentParser(description="Run the raw external dirty-public-corpus characterization suite.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def download(client: httpx.Client, source: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    started = time.perf_counter()
    response = client.get(source["url"])
    response.raise_for_status()
    payload = response.content
    if not payload:
        raise ValueError("empty response")
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    elapsed = time.perf_counter() - started
    return payload, {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(payload),
        "elapsed_seconds": round(elapsed, 3),
        "final_url": str(response.url),
    }


def evaluate_parse(parsed: Any, expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if parsed is None:
        return ["document did not parse"]
    if expected.get("document_type") and parsed.document_type != expected["document_type"]:
        failures.append(f"document_type expected {expected['document_type']!r}, got {parsed.document_type!r}")
    if expected.get("number") and parsed.number != expected["number"]:
        failures.append(f"number expected {expected['number']!r}, got {parsed.number!r}")
    minimum_lines = expected.get("minimum_lines")
    if minimum_lines is not None and len(parsed.lines) < int(minimum_lines):
        failures.append(f"minimum_lines expected >= {minimum_lines}, got {len(parsed.lines)}")
    if expected.get("currency") and parsed.currency != expected["currency"]:
        failures.append(f"currency expected {expected['currency']!r}, got {parsed.currency!r}")
    if expected.get("number_present") and not parsed.number:
        failures.append("document number missing")
    return failures


def markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report["cases"]:
        result = "PASS" if item["expectation_passed"] else "FAIL"
        parse_status = item["parse"]["status"]
        rows.append(
            f"| {item['id']} | {item['category']} | {parse_status} | {item['observed_sha256'][:12]} | {result} |"
        )
    failures = [item for item in report["cases"] if not item["expectation_passed"]]
    failure_lines = "\n".join(
        f"- `{item['id']}`: " + "; ".join(item["expectation_failures"] or ["expectation mismatch"])
        for item in failures
    ) or "- none"
    return f"""# Dirty Public Corpus 22 — characterization result

Generated: `{report['generated_at']}`  
Engine: `{report['product']['engine_version']}`  
Manifest frozen: **{str(report['manifest']['frozen']).lower()}**

## What this is

A raw external-document characterization suite. Files are downloaded as published and are not normalized into ThisTinti's preferred JSON schema before parsing. It is not a real company pilot and it is not an accuracy claim.

## Summary

- cases: **{report['metrics']['case_count']}**
- expectation passes: **{report['metrics']['expectation_passes']}**
- expectation failures: **{report['metrics']['expectation_failures']}**
- download failures: **{report['metrics']['download_failures']}**
- unhandled exceptions: **{report['metrics']['unhandled_exceptions']}**
- parsed: **{report['metrics']['parse_status_counts'].get('parsed', 0)}**
- structured rejections: **{report['metrics']['parse_status_counts'].get('parse_error', 0)}**
- gate: **{'PASS' if report['metrics']['gate_passed'] else 'FAIL'}**

| Case | Category | Parser result | SHA-256 | Expectation |
|---|---|---|---|---|
{chr(10).join(rows)}

## Current failures

{failure_lines}

## Governance boundary

A PASS here proves only the assertions encoded for these raw public/external files. It does not prove performance on arbitrary company folders, OCR-heavy scans, or a controlled authorized pilot.
"""


def run_case(client: httpx.Client, source: dict[str, Any], workdir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": source["id"],
        "category": source["category"],
        "publisher": source["publisher"],
        "source_url": source["url"],
        "filename": source["filename"],
        "source_commit": source.get("source_commit"),
        "github_blob_sha": source.get("github_blob_sha"),
        "expected_sha256": source.get("expected_sha256"),
        "observed_sha256": "",
        "download": {"status": "pending"},
        "parse": {"status": "pending"},
        "expectation_passed": False,
        "expectation_failures": [],
    }
    try:
        payload, download_metadata = download(client, source)
        result["observed_sha256"] = sha256_bytes(payload)
        result["download"] = {"status": "downloaded", **download_metadata}
    except (httpx.HTTPError, ValueError) as exc:
        result["download"] = {"status": "failed", "error": str(exc)}
        result["parse"] = {"status": "not_run"}
        result["expectation_failures"] = [f"download failed: {exc}"]
        return result

    expected_sha = source.get("expected_sha256")
    if expected_sha and result["observed_sha256"] != expected_sha:
        result["expectation_failures"].append(
            f"source SHA-256 mismatch: expected {expected_sha}, got {result['observed_sha256']}"
        )

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
        result["parse"] = {
            "status": "parsed",
            "document_type": parsed.document_type,
            "number": parsed.number,
            "document_date": None if parsed.document_date is None else str(parsed.document_date),
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
    except Exception as exc:  # noqa: BLE001 - benchmark must distinguish crashes from expected parse errors.
        result["parse"] = {
            "status": "unhandled_exception",
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }
        result["expectation_failures"].append(f"unhandled parser exception: {type(exc).__name__}: {exc}")
        return result

    expected = source.get("expected") or {}
    outcome = expected.get("outcome")
    if outcome == "parse":
        if parse_error is not None:
            result["expectation_failures"].append(f"expected parse, got ParseError: {parse_error}")
        else:
            result["expectation_failures"].extend(evaluate_parse(parsed, expected))
    elif outcome == "safe_rejection":
        if parse_error is None:
            result["expectation_failures"].append("expected a structured ParseError rejection, but document parsed")
    else:
        result["expectation_failures"].append(f"unknown expected outcome: {outcome!r}")

    result["expectation_passed"] = not result["expectation_failures"]
    return result


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    sources = manifest.get("sources") or []
    if len(sources) != 22:
        raise SystemExit(f"Dirty Public Corpus v1 must contain exactly 22 cases, got {len(sources)}")

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="thistinti-dirty-public-") as temp_dir:
        workdir = Path(temp_dir)
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(45.0),
            headers={"User-Agent": "ThisTinti-public-evidence-benchmark/1.0"},
        ) as client:
            cases = [run_case(client, source, workdir) for source in sources]

    parse_status_counts = Counter(item["parse"]["status"] for item in cases)
    download_failures = sum(item["download"]["status"] != "downloaded" for item in cases)
    unhandled = parse_status_counts.get("unhandled_exception", 0)
    expectation_failures = sum(not item["expectation_passed"] for item in cases)
    integrity_unfrozen = sum(
        1
        for source in sources
        if source["url"].startswith("https://www.portland.gov/") and not source.get("expected_sha256")
    )
    frozen = bool(manifest.get("frozen"))
    discovery_safe = download_failures == 0 and unhandled == 0
    gate_passed = discovery_safe and (not frozen or (expectation_failures == 0 and integrity_unfrozen == 0))

    report = {
        "schema": "thistinti.dirty-public-corpus-result.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product": {"name": "ThisTinti", "engine_version": RELEASE_VERSION},
        "manifest": {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "frozen": frozen,
            "evidence_level": manifest.get("evidence_level"),
            "real_company_pilot": False,
        },
        "metrics": {
            "case_count": len(cases),
            "expectation_passes": len(cases) - expectation_failures,
            "expectation_failures": expectation_failures,
            "download_failures": download_failures,
            "unhandled_exceptions": unhandled,
            "unfrozen_portland_sources": integrity_unfrozen,
            "parse_status_counts": dict(parse_status_counts),
            "gate_passed": gate_passed,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
        "cases": cases,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    for item in cases:
        if not item["expectation_passed"]:
            print(f"FAIL {item['id']}: {'; '.join(item['expectation_failures'])}")
        if item["source_url"].startswith("https://www.portland.gov/"):
            print(f"PORTLAND_SHA256 {item['id']} {item['observed_sha256']}")

    if not discovery_safe:
        return 2
    if frozen and not gate_passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
