#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.audit import add_audit  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Tenant, User  # noqa: E402
from app.security import hash_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first administrator in a closed self-hosted deployment")
    parser.add_argument("--organization", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()

    password = (
        sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Administrator password: ")
    )
    if not password:
        raise RuntimeError("Administrator password is required")
    password_hash = hash_password(password)
    email = args.email.lower().strip()
    organization = args.organization.strip()
    if not organization:
        raise RuntimeError("Organization name is required")

    with SessionLocal() as db:
        if int(db.scalar(select(func.count(User.id))) or 0) != 0:
            raise RuntimeError("Bootstrap refused: at least one user already exists")
        tenant = Tenant(name=organization)
        db.add(tenant)
        db.flush()
        user = User(tenant_id=tenant.id, email=email, password_hash=password_hash, role="admin")
        db.add(user)
        db.flush()
        add_audit(
            db,
            tenant.id,
            "tenant.bootstrap_admin_created",
            user.id,
            "user",
            user.id,
            {"organization": organization, "method": "offline-self-hosted-bootstrap"},
        )
        db.commit()
    print(f"First administrator created for {organization}: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
