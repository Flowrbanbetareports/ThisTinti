#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("THISTINTI_STAGING_URL"))
    parser.add_argument("--email", default=os.getenv("THISTINTI_STAGING_ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("THISTINTI_STAGING_ADMIN_PASSWORD"))
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--token-mode", action="store_true", help="Use bearer auth for non-browser CI probes")
    parser.add_argument("--report", default="staging-acceptance-report.json")
    args = parser.parse_args()

    if not all((args.base_url, args.email, args.password)):
        parser.error("base URL, email and password are required")

    base_url = args.base_url.rstrip("/")
    result: dict[str, object] = {
        "base_url": base_url,
        "started_at": time.time(),
        "checks": {},
    }
    checks = result["checks"]
    if not isinstance(checks, dict):
        raise RuntimeError("Internal acceptance-report state is invalid")

    with httpx.Client(base_url=base_url, timeout=20, follow_redirects=True) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        checks["health"] = health.json()

        if args.bootstrap:
            auth = client.post(
                "/api/auth/register",
                headers={"X-Session-Mode": "token"} if args.token_mode else None,
                json={
                    "organization_name": "ThisTinti Staging Acceptance",
                    "email": args.email,
                    "password": args.password,
                },
            )
            if auth.status_code not in (201, 409):
                auth.raise_for_status()
            if auth.status_code == 409:
                auth = client.post(
                    "/api/auth/login",
                    headers={"X-Session-Mode": "token"} if args.token_mode else None,
                    json={"email": args.email, "password": args.password},
                )
                auth.raise_for_status()
        else:
            auth = client.post(
                "/api/auth/login",
                headers={"X-Session-Mode": "token"} if args.token_mode else None,
                json={"email": args.email, "password": args.password},
            )
            auth.raise_for_status()

        if args.token_mode:
            token = auth.json().get("token")
            if not token:
                raise RuntimeError("Bearer token not issued")
            headers = {"Authorization": f"Bearer {token}"}
        else:
            csrf = client.cookies.get("thistinti_csrf")
            if not csrf:
                raise RuntimeError("CSRF cookie not issued")
            headers = {"X-CSRF-Token": csrf, "Origin": base_url}

        demo = client.post("/api/demo/load", headers=headers)
        demo.raise_for_status()
        checks["demo"] = demo.json()

        deadline = time.monotonic() + args.readiness_timeout
        while True:
            readiness = client.get("/api/readiness")
            if readiness.status_code == 200 and readiness.json().get("ready"):
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"readiness timeout: {readiness.text}")
            time.sleep(2)
        checks["readiness"] = readiness.json()

        dashboard = client.get("/api/dashboard", headers=headers)
        dashboard.raise_for_status()
        checks["dashboard"] = dashboard.json()

        audit = client.get("/api/audit/verify", headers=headers)
        audit.raise_for_status()
        checks["audit"] = audit.json()

        if not audit.json().get("valid"):
            raise RuntimeError("audit chain invalid")
        if dashboard.json().get("documents", 0) < 4:
            raise RuntimeError("demo documents missing")

    result["passed"] = True
    result["completed_at"] = time.time()
    Path(args.report).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Staging acceptance failed: {exc}", file=sys.stderr)
        raise
