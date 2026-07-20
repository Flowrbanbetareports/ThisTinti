#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def child_command(executable: Path | None, mode: str, data_dir: Path, port: int) -> list[str]:
    flag = "--server" if mode == "server" else "--worker"
    if executable:
        return [str(executable), flag, "--data-dir", str(data_dir), "--port", str(port)]
    return [sys.executable, "-m", "app.local_launcher", flag, "--data-dir", str(data_dir), "--port", str(port)]


def stop(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_json(client: httpx.Client, path: str, predicate, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    last: object = None
    while time.monotonic() < deadline:
        try:
            response = client.get(path)
            last = response.text
            if response.status_code < 500:
                payload = response.json()
                last = payload
                if predicate(response, payload):
                    return payload
        except (httpx.HTTPError, ValueError) as exc:
            last = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"Timeout su {path}; ultimo risultato: {last}")


def start_pair(executable: Path | None, data_dir: Path, port: int, logs: Path):
    logs.mkdir(parents=True, exist_ok=True)
    server_log = (logs / "server.log").open("ab", buffering=0)
    worker_log = (logs / "worker.log").open("ab", buffering=0)
    server = subprocess.Popen(  # nosec B603
        child_command(executable, "server", data_dir, port),
        cwd=ROOT,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10.0)
    wait_json(
        client,
        "/api/health",
        lambda response, payload: response.status_code == 200 and payload.get("edition") == "local",
    )
    worker = subprocess.Popen(  # nosec B603
        child_command(executable, "worker", data_dir, port),
        cwd=ROOT,
        stdout=worker_log,
        stderr=subprocess.STDOUT,
    )
    wait_json(
        client, "/api/readiness", lambda response, payload: response.status_code == 200 and payload.get("ready") is True
    )
    return server, worker, client, server_log, worker_log


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end smoke for ThisTinti Local Edition")
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()

    executable = args.executable.resolve() if args.executable else None
    if executable and not executable.exists():
        raise SystemExit(f"Executable not found: {executable}")

    temporary = None
    if args.data_dir:
        data_dir = args.data_dir.resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="thistinti-local-smoke-")
        data_dir = Path(temporary.name)
    port = free_port()
    logs = data_dir / "smoke-logs"
    report: dict[str, object] = {"port": port, "data_dir": str(data_dir), "frozen": bool(executable)}
    smoke_password = f"Smoke-{secrets.token_urlsafe(18)}-9aA!"

    server = worker = None
    client = None
    handles = []
    try:
        server, worker, client, *handles = start_pair(executable, data_dir, port, logs)
        registration = client.post(
            "/api/auth/register",
            headers={"X-Session-Mode": "token"},
            json={
                "organization_name": "Local Smoke Company",
                "email": "local-smoke@example.com",
                "password": smoke_password,
                "legal_notice_version": "2026-07-20-v2",
                "accepted_terms": True,
                "accepted_specific_clauses": True,
            },
        )
        registration.raise_for_status()
        token = registration.json()["token"]
        auth = {"Authorization": f"Bearer {token}"}
        sample = ROOT / "samples" / "proposal.json"
        with sample.open("rb") as source:
            queued = client.post(
                "/api/jobs/documents",
                headers={**auth, "Idempotency-Key": "local-distribution-smoke-proposal"},
                files={"file": ("proposal.json", source, "application/json")},
                data={"document_type": "proposal"},
            )
        queued.raise_for_status()
        job_id = queued.json()["job"]["id"]
        job = wait_json(
            client,
            f"/api/jobs/{job_id}",
            lambda response, payload: response.status_code == 200 and payload.get("status") in {"completed", "failed"},
        )
        if job["status"] != "completed":
            raise RuntimeError(f"Local worker failed: {job}")
        documents = client.get("/api/documents", headers=auth)
        documents.raise_for_status()
        original_documents = documents.json()
        if len(original_documents) != 1:
            raise RuntimeError(f"Expected one document, got {len(original_documents)}")
        report["first_run"] = {"job": job["status"], "documents": len(original_documents)}

        client.close()
        client = None
        stop(worker)
        stop(server)
        for handle in handles:
            handle.close()
        handles = []
        server = worker = None

        server, worker, client, *handles = start_pair(executable, data_dir, port, logs)
        login = client.post(
            "/api/auth/login",
            headers={"X-Session-Mode": "token"},
            json={"email": "local-smoke@example.com", "password": smoke_password},
        )
        login.raise_for_status()
        auth = {"Authorization": f"Bearer {login.json()['token']}"}
        persisted = client.get("/api/documents", headers=auth)
        persisted.raise_for_status()
        persisted_documents = persisted.json()
        if len(persisted_documents) != 1 or persisted_documents[0]["id"] != original_documents[0]["id"]:
            raise RuntimeError("Document persistence check failed after restart")
        report["restart"] = {"documents": len(persisted_documents), "same_document": True}
        report["passed"] = True
    finally:
        if client:
            client.close()
        stop(worker)
        stop(server)
        for handle in handles:
            handle.close()
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if temporary:
            temporary.cleanup()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
