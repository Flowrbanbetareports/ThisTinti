#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx


def required(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def login(client: httpx.Client, email: str, password: str, *, bootstrap: bool) -> dict:
    if bootstrap:
        response = client.post(
            "/api/auth/register",
            json={
                "organization_name": "ThisTinti External Proof",
                "email": email,
                "password": password,
            },
        )
        if response.status_code == 409:
            response = client.post("/api/auth/login", json={"email": email, "password": password})
    else:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    csrf = client.cookies.get("thistinti_csrf")
    session = client.cookies.get("thistinti_session")
    if not csrf or not session:
        raise RuntimeError("Browser session cookies were not issued")
    return {"X-CSRF-Token": csrf, "Origin": str(client.base_url).rstrip("/")}


def wait_ready(client: httpx.Client, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            response = client.get("/api/readiness")
            last = response.text
            if response.status_code == 200 and response.json().get("ready"):
                return response.json()
        except httpx.HTTPError as exc:
            last = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Readiness timeout: {last}")


def _queue_document(
    client: httpx.Client, headers: dict[str, str], source: dict, filename: str, key: str
) -> tuple[dict, bytes]:
    raw = json.dumps(source, ensure_ascii=False, separators=(",", ":")).encode()
    queued = client.post(
        "/api/jobs/documents",
        headers={**headers, "Idempotency-Key": key},
        files={"file": (filename, raw, "application/json")},
    )
    queued.raise_for_status()
    job_id = queued.json()["job"]["id"]
    deadline = time.monotonic() + 90
    job: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        if job.get("status") == "completed":
            return job, raw
        if job.get("status") in {"failed", "cancelled"}:
            raise RuntimeError(f"Processing job did not complete: {job}")
        time.sleep(1)
    raise RuntimeError(f"Processing job timeout: {job}")


def bootstrap(client: httpx.Client, email: str, password: str, state_path: Path) -> dict:
    health = client.get("/api/health")
    health.raise_for_status()
    headers = login(client, email, password, bootstrap=True)
    sources = [
        (
            "external-proof-proposal.json",
            "external-cloud-proof-proposal-001",
            {
                "document_type": "proposal",
                "number": "CLOUD-PROOF-001",
                "document_date": "2026-07-01",
                "supplier_name": "External Proof Supplier",
                "currency": "EUR",
                "lines": [
                    {"sku": "PROOF-A", "quantity": 2, "unit_price": 15.50},
                    {"sku": "PROOF-B", "quantity": 1, "unit_price": 9.00},
                ],
            },
        ),
        (
            "external-proof-invoice.json",
            "external-cloud-proof-invoice-001",
            {
                "document_type": "invoice",
                "number": "CLOUD-INV-001",
                "document_date": "2026-07-05",
                "supplier_name": "External Proof Supplier",
                "currency": "EUR",
                "references": {"order_numbers": ["CLOUD-PROOF-001"]},
                "lines": [
                    {"sku": "PROOF-A", "quantity": 2, "unit_price": 15.50},
                    {"sku": "PROOF-B", "quantity": 1, "unit_price": 9.00},
                ],
            },
        ),
        (
            "external-proof-payment.json",
            "external-cloud-proof-payment-001",
            {
                "document_type": "payment",
                "number": "CLOUD-PAY-001",
                "document_date": "2026-07-06",
                "supplier_name": "External Proof Supplier",
                "currency": "EUR",
                "references": {"invoice_numbers": ["CLOUD-INV-001"]},
                "lines": [{"description": "Pagamento CLOUD-INV-001", "quantity": 1, "unit_price": 40.00}],
            },
        ),
    ]
    documents: list[dict] = []
    jobs: list[dict] = []
    source_hashes: dict[str, str] = {}
    for filename, key, source in sources:
        job, raw = _queue_document(client, headers, source, filename, key)
        document_id = job["result"]["document_id"]
        document = client.get(f"/api/documents/{document_id}")
        document.raise_for_status()
        stored = client.get(f"/api/documents/{document_id}/file")
        stored.raise_for_status()
        digest = hashlib.sha256(raw).hexdigest()
        if hashlib.sha256(stored.content).hexdigest() != digest:
            raise RuntimeError(f"Stored file differs from source: {filename}")
        documents.append({"id": document_id, "number": document.json().get("number"), "filename": filename})
        jobs.append({"id": job["id"], "status": job["status"]})
        source_hashes[document_id] = digest

    chains = client.get("/api/chains")
    chains.raise_for_status()
    matching = [chain for chain in chains.json() if chain.get("reference_key") == "CLOUDPROOF001"]
    if len(matching) != 1:
        raise RuntimeError(f"Expected one reconstructed chain, got {matching}")
    chain_id = matching[0]["id"]
    intelligence = client.get(f"/api/chains/{chain_id}/intelligence")
    intelligence.raise_for_status()
    intelligence_body = intelligence.json()
    roles = {node.get("role") for node in intelligence_body["proof_graph"]["nodes"]}
    if not {"proposal", "invoice", "payment"}.issubset(roles):
        raise RuntimeError(f"Proof Graph is missing expected roles: {roles}")
    simulation = client.post(
        f"/api/chains/{chain_id}/simulate",
        headers=headers,
        json={"action": "approve_invoice"},
    )
    simulation.raise_for_status()
    red_team = client.post(f"/api/chains/{chain_id}/red-team", headers=headers)
    red_team.raise_for_status()
    if red_team.json().get("coverage", 0) <= 0:
        raise RuntimeError("Self-red-team returned no coverage")

    readiness = wait_ready(client)
    audit = client.get("/api/audit/verify")
    audit.raise_for_status()
    if not audit.json().get("valid"):
        raise RuntimeError("Audit chain invalid before restart")
    state = {
        "chain_id": chain_id,
        "documents": documents,
        "jobs": jobs,
        "source_hashes": source_hashes,
        "created_at": time.time(),
    }
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return {
        "phase": "bootstrap",
        "health": health.json(),
        "chain_id": chain_id,
        "documents": documents,
        "jobs": jobs,
        "proof_graph_roles": sorted(role for role in roles if role),
        "risk_decision": simulation.json().get("decision"),
        "risk_score": simulation.json().get("score"),
        "red_team_coverage": red_team.json().get("coverage"),
        "readiness": readiness,
        "audit_valid": True,
    }


def verify(client: httpx.Client, email: str, password: str, state_path: Path) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    health = client.get("/api/health")
    health.raise_for_status()
    login(client, email, password, bootstrap=False)
    persisted_documents = []
    for document_state in state["documents"]:
        document_id = document_state["id"]
        document = client.get(f"/api/documents/{document_id}")
        document.raise_for_status()
        stored = client.get(f"/api/documents/{document_id}/file")
        stored.raise_for_status()
        digest = hashlib.sha256(stored.content).hexdigest()
        if digest != state["source_hashes"][document_id]:
            raise RuntimeError(f"Stored file did not persist unchanged: {document_state['filename']}")
        persisted_documents.append({"id": document_id, "number": document.json().get("number")})
    for job_state in state["jobs"]:
        job = client.get(f"/api/jobs/{job_state['id']}")
        job.raise_for_status()
        if job.json().get("status") != "completed":
            raise RuntimeError("Completed processing job did not persist across restart")
    intelligence = client.get(f"/api/chains/{state['chain_id']}/intelligence")
    intelligence.raise_for_status()
    roles = {node.get("role") for node in intelligence.json()["proof_graph"]["nodes"]}
    if not {"proposal", "invoice", "payment"}.issubset(roles):
        raise RuntimeError("Proof Graph did not persist across restart")
    readiness = wait_ready(client)
    audit = client.get("/api/audit/verify")
    audit.raise_for_status()
    if not audit.json().get("valid"):
        raise RuntimeError("Audit chain invalid after restart")
    return {
        "phase": "verify_after_restart",
        "health": health.json(),
        "chain_id": state["chain_id"],
        "documents": persisted_documents,
        "job_statuses": ["completed" for _ in state["jobs"]],
        "proof_graph_roles": sorted(role for role in roles if role),
        "readiness": readiness,
        "audit_valid": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the external ThisTinti cloud proof")
    parser.add_argument("phase", choices=("bootstrap", "verify"))
    parser.add_argument("--base-url", default=os.getenv("THISTINTI_PROOF_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--email", default=os.getenv("THISTINTI_PROOF_EMAIL", "proof@thistinti.example.com"))
    parser.add_argument("--password", default=os.getenv("THISTINTI_PROOF_PASSWORD"))
    parser.add_argument("--state", default="external-proof-state.json")
    parser.add_argument("--report", default="external-proof-report.json")
    args = parser.parse_args()
    password = required(args.password, "THISTINTI_PROOF_PASSWORD")
    state_path = Path(args.state)
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=20, follow_redirects=True) as client:
        if args.phase == "bootstrap":
            result = bootstrap(client, args.email, password, state_path)
        else:
            result = verify(client, args.email, password, state_path)
    report_path = Path(args.report)
    history = []
    if report_path.exists():
        history = json.loads(report_path.read_text(encoding="utf-8")).get("phases", [])
    report = {
        "passed": args.phase == "verify",
        "base_url": args.base_url,
        "phases": [*history, result],
        "updated_at": time.time(),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"External cloud proof failed: {exc}", file=sys.stderr)
        raise
