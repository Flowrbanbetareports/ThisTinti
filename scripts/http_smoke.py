#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix="thistinti-http-smoke-") as tmp:
        root = Path(tmp)
        port = free_port()
        env = os.environ.copy()
        env.update(
            {
                "THISTINTI_ENV": "test",
                "THISTINTI_DATABASE_URL": f"sqlite:///{root / 'smoke.db'}",
                "THISTINTI_STORAGE_DIR": str(root / "uploads"),
                "THISTINTI_SECRET_KEY": secrets.token_urlsafe(48),
                "THISTINTI_AUTO_CREATE_SCHEMA": "false",
                "THISTINTI_ALLOW_REGISTRATION": "true",
                "THISTINTI_SECURE_COOKIES": "false",
                "THISTINTI_CORS_ORIGINS": f"http://127.0.0.1:{port}",
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
        log_path = root / "uvicorn.log"
        with log_path.open("wb") as log:
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
                    "warning",
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                base_url = f"http://127.0.0.1:{port}"
                with httpx.Client(base_url=base_url, timeout=10.0) as client:
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            response = client.get("/api/health")
                            if response.status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if process.poll() is not None:
                            raise RuntimeError(log_path.read_text(encoding="utf-8", errors="replace"))
                        if time.monotonic() >= deadline:
                            raise RuntimeError("HTTP smoke server did not become ready")
                        time.sleep(0.2)

                    registration = client.post(
                        "/api/auth/register",
                        json={
                            "organization_name": "ThisTinti HTTP Smoke",
                            "email": "smoke@thistinti.it",
                            "password": "Smoke-" + secrets.token_urlsafe(24),
                        },
                    )
                    registration.raise_for_status()
                    csrf = client.cookies.get("thistinti_csrf")
                    if not csrf or not client.cookies.get("thistinti_session"):
                        raise RuntimeError("Secure browser session cookies were not issued")
                    headers = {"X-CSRF-Token": csrf, "Origin": base_url}
                    loaded = client.post("/api/demo/load", headers=headers)
                    loaded.raise_for_status()
                    dashboard = client.get("/api/dashboard")
                    dashboard.raise_for_status()
                    readiness = client.get("/api/readiness")
                    readiness.raise_for_status()
                    audit = client.get("/api/audit/verify")
                    audit.raise_for_status()
                    payload = {
                        "demo_loaded": loaded.json().get("loaded"),
                        "documents": dashboard.json().get("documents"),
                        "chains": dashboard.json().get("chains"),
                        "open_cases": dashboard.json().get("cases_open"),
                        "readiness": readiness.json().get("ready"),
                        "audit_valid": audit.json().get("valid"),
                    }
                    if (
                        payload["demo_loaded"] != 4
                        or payload["documents"] != 4
                        or payload["chains"] != 1
                        or not payload["open_cases"]
                        or not payload["readiness"]
                        or not payload["audit_valid"]
                    ):
                        raise RuntimeError(f"Unexpected HTTP smoke result: {payload}")
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
