#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


async def run_probe(
    *, base_url: str, paths: list[str], requests: int, concurrency: int, timeout: float
) -> dict[str, Any]:
    queue: asyncio.Queue[int] = asyncio.Queue()
    for index in range(requests):
        queue.put_nowait(index)

    latencies_ms: list[float] = []
    errors: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    started = time.perf_counter()

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, limits=limits, follow_redirects=True) as client:

        async def worker(worker_id: int) -> None:
            while True:
                try:
                    request_index = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                path = paths[request_index % len(paths)]
                request_started = time.perf_counter()
                try:
                    response = await client.get(path, headers={"X-Load-Probe": "beta-readiness"})
                    elapsed_ms = (time.perf_counter() - request_started) * 1000
                    latencies_ms.append(elapsed_ms)
                    key = str(response.status_code)
                    status_counts[key] = status_counts.get(key, 0) + 1
                    if response.status_code >= 400:
                        errors.append(
                            {
                                "worker": worker_id,
                                "path": path,
                                "status": response.status_code,
                                "detail": response.text[:200],
                            }
                        )
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - request_started) * 1000
                    latencies_ms.append(elapsed_ms)
                    errors.append({"worker": worker_id, "path": path, "error": type(exc).__name__, "detail": str(exc)})
                finally:
                    queue.task_done()

        await asyncio.gather(*(worker(worker_id) for worker_id in range(concurrency)))

    duration_seconds = time.perf_counter() - started
    completed = requests - len(errors)
    return {
        "schema": "thistinti.beta-load-probe.v1",
        "base_url": base_url,
        "paths": paths,
        "requested": requests,
        "completed_without_error": completed,
        "concurrency": concurrency,
        "duration_seconds": round(duration_seconds, 3),
        "throughput_requests_per_second": round(requests / duration_seconds, 2) if duration_seconds else 0.0,
        "error_count": len(errors),
        "error_rate": round(len(errors) / requests, 6),
        "status_counts": status_counts,
        "latency_ms": {
            "minimum": round(min(latencies_ms), 2) if latencies_ms else 0.0,
            "mean": round(statistics.fmean(latencies_ms), 2) if latencies_ms else 0.0,
            "p50": round(percentile(latencies_ms, 0.50), 2),
            "p95": round(percentile(latencies_ms, 0.95), 2),
            "p99": round(percentile(latencies_ms, 0.99), 2),
            "maximum": round(max(latencies_ms), 2) if latencies_ms else 0.0,
        },
        "errors": errors[:25],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded non-destructive load regression probe.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", action="append", dest="paths", help="GET path; may be repeated")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-p95-ms", type=float, default=750.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--report", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.requests < 1 or args.concurrency < 1 or args.concurrency > args.requests:
        print("Invalid requests/concurrency configuration", file=sys.stderr)
        return 2
    paths = args.paths or ["/api/health", "/"]
    if any(not path.startswith("/") for path in paths):
        print("Every path must start with /", file=sys.stderr)
        return 2

    report = asyncio.run(
        run_probe(
            base_url=args.base_url.rstrip("/"),
            paths=paths,
            requests=args.requests,
            concurrency=args.concurrency,
            timeout=args.timeout,
        )
    )
    report["thresholds"] = {"max_p95_ms": args.max_p95_ms, "max_error_rate": args.max_error_rate}
    report["passed"] = report["latency_ms"]["p95"] <= args.max_p95_ms and report["error_rate"] <= args.max_error_rate
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
