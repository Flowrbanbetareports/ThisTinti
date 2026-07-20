#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import stat
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LEGAL_NOTICE_VERSION = "2026-07-20-v2"
LEGAL_FILES = ("LICENSE", "TERMS_OF_USE.md", "DISCLAIMER.md", "PRIVACY.md", "TRADEMARKS.md", "SUPPORT.md")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[A-Za-z]{2,63}$")


def _write_secret(path: Path, value: str) -> None:
    path.write_text(value + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in LEGAL_FILES}


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize an operator-managed ThisTinti self-hosted deployment")
    parser.add_argument("--directory", type=Path, default=ROOT / "deploy" / "enterprise")
    parser.add_argument("--host", required=True, help="Public DNS name, for example thistinti.example.com")
    parser.add_argument("--deployment-id", default="")
    parser.add_argument("--accept-operator-responsibility", action="store_true")
    parser.add_argument("--accept-no-support", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    host = args.host.strip().lower()
    if not HOST_RE.fullmatch(host):
        raise RuntimeError(
            "--host must be a valid DNS name; IP-only and localhost deployments require manual proxy changes"
        )
    if not args.accept_operator_responsibility or not args.accept_no_support:
        raise RuntimeError(
            "Initialization requires both explicit acknowledgements: operator responsibility and no guaranteed support"
        )

    directory = args.directory.resolve()
    secrets_dir = directory / "secrets"
    if (directory / ".env").exists() and not args.overwrite:
        raise RuntimeError(
            f"{directory / '.env'} already exists; pass --overwrite only after preserving the deployment"
        )
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (directory / "backups").mkdir(parents=True, exist_ok=True)
    (directory / "logs").mkdir(parents=True, exist_ok=True)
    for protected in (secrets_dir, directory / "backups", directory / "logs"):
        protected.chmod(stat.S_IRWXU)

    admin_password = secrets.token_urlsafe(48)
    owner_password = secrets.token_urlsafe(48)
    app_password = secrets.token_urlsafe(48)
    app_secret = secrets.token_urlsafe(64)
    deployment_id = args.deployment_id.strip() or f"selfhost-{secrets.token_hex(8)}"

    _write_secret(secrets_dir / "postgres_admin_password.txt", admin_password)
    _write_secret(secrets_dir / "db_owner_password.txt", owner_password)
    _write_secret(secrets_dir / "db_app_password.txt", app_password)
    _write_secret(secrets_dir / "app_secret_key.txt", app_secret)
    _write_secret(
        secrets_dir / "postgres_admin_url.txt",
        f"postgresql://postgres:{quote(admin_password, safe='')}@db:5432/thistinti",
    )
    _write_secret(
        secrets_dir / "database_owner_url.txt",
        f"postgresql+psycopg://thistinti_owner:{quote(owner_password, safe='')}@db:5432/thistinti",
    )
    _write_secret(
        secrets_dir / "database_app_url.txt",
        f"postgresql+psycopg://thistinti_app:{quote(app_password, safe='')}@db:5432/thistinti",
    )

    env = f"""# Generated locally by scripts/enterprise_init.py. Do not commit this file.\nTHISTINTI_PUBLIC_HOST={host}\nTHISTINTI_DEPLOYMENT_ID={deployment_id}\nTHISTINTI_CORS_ORIGINS=https://{host}\nTHISTINTI_OPERATOR_ACCEPTS_SELF_HOSTING_RESPONSIBILITY=true\nTHISTINTI_OPERATOR_ACCEPTS_NO_SUPPORT=true\nTHISTINTI_WORKER_REPLICAS=2\nTHISTINTI_COMPLETED_JOB_RETENTION_DAYS=30\nTHISTINTI_QUARANTINE_RETENTION_HOURS=24\n"""
    (directory / ".env").write_text(env, encoding="utf-8")
    (directory / ".env").chmod(stat.S_IRUSR | stat.S_IWUSR)

    acceptance = {
        "format": "thistinti-self-hosted-operator-acceptance-v1",
        "legal_notice_version": LEGAL_NOTICE_VERSION,
        "specific_clauses": ["3", "4", "5", "7", "8", "9", "10", "11", "12", "13"],
        "accepted_at": datetime.now(UTC).isoformat(),
        "deployment_id": deployment_id,
        "public_host": host,
        "operator_accepts_self_hosting_responsibility": True,
        "operator_accepts_no_guaranteed_support_or_sla": True,
        "operator_controls_infrastructure_and_data": True,
        "transmitted_to_author": False,
        "legal_document_hashes": _hashes(),
    }
    path = directory / "operator-acceptance.json"
    path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(json.dumps({"initialized": True, "directory": str(directory), "deployment_id": deployment_id}, indent=2))
    print("Next: python scripts/enterprise_preflight.py --directory deploy/enterprise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
