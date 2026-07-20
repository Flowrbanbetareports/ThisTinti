#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LEGAL_NOTICE_VERSION = "2026-07-20-v2"
LEGAL_FILES = ("LICENSE", "TERMS_OF_USE.md", "DISCLAIMER.md", "PRIVACY.md", "TRADEMARKS.md", "SUPPORT.md")
REQUIRED_SECRETS = (
    "postgres_admin_password.txt",
    "db_owner_password.txt",
    "db_app_password.txt",
    "app_secret_key.txt",
    "postgres_admin_url.txt",
    "database_owner_url.txt",
    "database_app_url.txt",
)


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError(f"Invalid line in {path.name}: {raw}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed preflight for the operator-managed self-hosted deployment"
    )
    parser.add_argument("--directory", type=Path, default=ROOT / "deploy" / "enterprise")
    args = parser.parse_args()
    directory = args.directory.resolve()
    failures: list[str] = []

    env_path = directory / ".env"
    acceptance_path = directory / "operator-acceptance.json"
    compose_path = directory / "docker-compose.enterprise.yml"
    for path in (env_path, acceptance_path, compose_path, directory / "Caddyfile"):
        if not path.is_file():
            failures.append(f"missing required file: {path}")
    if failures:
        raise RuntimeError("; ".join(failures))

    env = _load_env(env_path)
    for key in (
        "THISTINTI_PUBLIC_HOST",
        "THISTINTI_DEPLOYMENT_ID",
        "THISTINTI_CORS_ORIGINS",
        "THISTINTI_OPERATOR_ACCEPTS_SELF_HOSTING_RESPONSIBILITY",
        "THISTINTI_OPERATOR_ACCEPTS_NO_SUPPORT",
    ):
        if not env.get(key):
            failures.append(f"missing {key} in .env")
    if env.get("THISTINTI_OPERATOR_ACCEPTS_SELF_HOSTING_RESPONSIBILITY") != "true":
        failures.append("operator responsibility acknowledgement is not true")
    if env.get("THISTINTI_OPERATOR_ACCEPTS_NO_SUPPORT") != "true":
        failures.append("no-support acknowledgement is not true")
    host = env.get("THISTINTI_PUBLIC_HOST", "")
    if env.get("THISTINTI_CORS_ORIGINS") != f"https://{host}":
        failures.append("CORS origin must exactly match the HTTPS public host")
    if len(env.get("THISTINTI_DEPLOYMENT_ID", "")) < 8:
        failures.append("deployment id is too short")
    replicas = env.get("THISTINTI_WORKER_REPLICAS", "2")
    if not replicas.isdigit() or not (1 <= int(replicas) <= 32):
        failures.append("THISTINTI_WORKER_REPLICAS must be between 1 and 32")

    secrets_dir = directory / "secrets"
    secret_values: dict[str, str] = {}
    for name in REQUIRED_SECRETS:
        path = secrets_dir / name
        if not path.is_file():
            failures.append(f"missing secret: {name}")
            continue
        value = path.read_text(encoding="utf-8").strip()
        secret_values[name] = value
        if not value:
            failures.append(f"empty secret: {name}")
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            failures.append(f"secret permissions are too broad: {name}")
    passwords = [secret_values.get(name, "") for name in REQUIRED_SECRETS[:4]]
    if any(len(value) < 40 for value in passwords):
        failures.append("generated passwords and application secret must be at least 40 characters")
    if len(set(passwords)) != len(passwords):
        failures.append("database and application secrets must be distinct")
    for name in REQUIRED_SECRETS[4:]:
        value = secret_values.get(name, "")
        parsed = urlparse(value.replace("postgresql+psycopg://", "postgresql://", 1))
        if parsed.scheme != "postgresql" or parsed.hostname != "db" or parsed.path != "/thistinti":
            failures.append(f"invalid internal database URL: {name}")

    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    if acceptance.get("legal_notice_version") != LEGAL_NOTICE_VERSION:
        failures.append("operator acceptance legal notice version is obsolete")
    if acceptance.get("deployment_id") != env.get("THISTINTI_DEPLOYMENT_ID"):
        failures.append("operator acceptance deployment id does not match .env")
    if acceptance.get("public_host") != host:
        failures.append("operator acceptance host does not match .env")
    if acceptance.get("operator_accepts_self_hosting_responsibility") is not True:
        failures.append("operator acceptance does not record responsibility")
    if acceptance.get("operator_accepts_no_guaranteed_support_or_sla") is not True:
        failures.append("operator acceptance does not record no-support terms")
    expected_hashes = {name: _sha(ROOT / name) for name in LEGAL_FILES}
    if acceptance.get("legal_document_hashes") != expected_hashes:
        failures.append("legal documents changed after operator acceptance; re-run enterprise_init.py")

    compose_text = compose_path.read_text(encoding="utf-8")
    for marker in (
        'THISTINTI_SELF_HOSTED_REFERENCE: "true"',
        'THISTINTI_ALLOW_REGISTRATION: "false"',
        'THISTINTI_REQUIRE_MALWARE_SCANNER: "true"',
        "database_app_url",
        "operator-acceptance.json",
        "internal: true",
    ):
        if marker not in compose_text:
            failures.append(f"enterprise compose safety marker missing: {marker}")

    result = {
        "ready": not failures,
        "deployment_id": env.get("THISTINTI_DEPLOYMENT_ID"),
        "public_host": host,
        "worker_replicas": int(replicas) if replicas.isdigit() else None,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
