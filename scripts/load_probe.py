#!/usr/bin/env python3
"""Small local concurrency probe, not a production capacity certification."""

from __future__ import annotations

import concurrent.futures
import json
import os
import secrets
import socket
import statistics
import subprocess  # nosec B404
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "load-probe.json"
REQUESTS = 300
WORKERS = 16
_thread_local = threading.local()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[position]


def worker(base_url: str, token: str, index: int) -> tuple[int, float]:
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = httpx.Client(base_url=base_url, timeout=10.0, headers={"Authorization": f"Bearer {token}"})
        _thread_local.client = client
    path = "/api/dashboard" if index % 4 else "/api/health"
    started = time.perf_counter()
    response = client.get(path)
    elapsed = (time.perf_counter() - started) * 1000
    return response.status_code, elapsed


def main() -> int:
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix="thistinti-load-probe-") as tmp:
        root = Path(tmp)
        port = free_port()
        env = os.environ.copy()
        env.update(
            {
                "THISTINTI_ENV": "test",
                "THISTINTI_DATABASE_URL": f"sqlite:///{root / 'probe.db'}",
                "THISTINTI_STORAGE_DIR": str(root / "uploads"),
                "THISTINTI_SECRET_KEY": secrets.token_urlsafe(48),
                "THISTINTI_AUTO_CREATE_SCHEMA": "false",
                "THISTINTI_ALLOW_REGISTRATION": "true",
                "THISTINTI_SECURE_COOKIES": "false",
            }
        )
        subprocess.run(  # nosec B603
            [python, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=env,
            check=True,
            timeout=60,
            stdout=subprocess.DEVNULL,
        )
        process = subprocess.Popen(  # nosec B603
            [
                python,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "error",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            with httpx.Client(base_url=base_url, timeout=10.0) as bootstrap:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        if bootstrap.get("/api/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("Load probe server unavailable")
                    time.sleep(0.2)
                registration = bootstrap.post(
                    "/api/auth/register",
                    headers={"X-Session-Mode": "token"},
                    json={
                        "organization_name": "ThisTinti Load Probe",
                        "email": "load-probe@thistinti.it",
                        "password": "Probe-" + secrets.token_urlsafe(24),
                    },
                )
                registration.raise_for_status()
                token = registration.json()["token"]

            started = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
                results = list(pool.map(lambda idx: worker(base_url, token, idx), range(REQUESTS)))
            duration = time.perf_counter() - started
            statuses = [status for status, _ in results]
            latencies = [latency for _, latency in results]
            success = sum(1 for status in statuses if status == 200)
            payload = {
                "scope": "local single-process SQLite read probe; not a production capacity claim",
                "requests": REQUESTS,
                "workers": WORKERS,
                "success": success,
                "errors": REQUESTS - success,
                "duration_seconds": round(duration, 3),
                "requests_per_second": round(REQUESTS / duration, 2),
                "latency_ms": {
                    "mean": round(statistics.fmean(latencies), 2),
                    "p50": round(percentile(latencies, 0.50), 2),
                    "p95": round(percentile(latencies, 0.95), 2),
                    "max": round(max(latencies), 2),
                },
            }
            OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0 if success == REQUESTS else 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
