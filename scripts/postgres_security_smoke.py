#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, set_tenant_context  # noqa: E402
from app.models import Document, DocumentLine, Supplier, Tenant, User  # noqa: E402
from app.security import hash_password  # noqa: E402


def ident() -> str:
    return str(uuid.uuid4())


def main() -> int:
    if not os.getenv("THISTINTI_DATABASE_URL", "").startswith("postgresql"):
        raise RuntimeError("This smoke test requires PostgreSQL")

    with SessionLocal() as db:
        role = db.execute(
            text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        if role.rolsuper or role.rolbypassrls:
            raise RuntimeError(
                f"PostgreSQL smoke must use a least-privilege runtime role; {role.current_user} bypasses RLS"
            )

    tenant_a = ident()
    tenant_b = ident()
    supplier_a = ident()
    supplier_b = ident()
    document_a = ident()

    with SessionLocal() as db:
        db.add_all(
            [
                Tenant(id=tenant_a, name="Tenant A"),
                Tenant(id=tenant_b, name="Tenant B"),
                User(
                    id=ident(),
                    tenant_id=tenant_a,
                    email=f"a-{ident()}@example.test",
                    password_hash=hash_password("Strong-Postgres-Smoke-1!"),
                    role="admin",
                ),
                User(
                    id=ident(),
                    tenant_id=tenant_b,
                    email=f"b-{ident()}@example.test",
                    password_hash=hash_password("Strong-Postgres-Smoke-2!"),
                    role="admin",
                ),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        set_tenant_context(db, tenant_a)
        db.add(Supplier(id=supplier_a, tenant_id=tenant_a, legal_name="Supplier A", normalized_name="supplier a"))
        db.add(
            Document(
                id=document_a,
                tenant_id=tenant_a,
                supplier_id=supplier_a,
                document_type="invoice",
                number="A-1",
                source_filename="a.json",
                storage_path="smoke/a.json",
                file_hash="a" * 64,
                parse_status="parsed",
                confidence=1.0,
            )
        )
        db.add(
            DocumentLine(
                tenant_id=tenant_a,
                document_id=document_a,
                line_no=1,
                quantity=Decimal("1"),
                unit_price=Decimal("10"),
                line_total=Decimal("10"),
            )
        )
        db.commit()

    with SessionLocal() as db:
        set_tenant_context(db, tenant_b)
        db.add(Supplier(id=supplier_b, tenant_id=tenant_b, legal_name="Supplier B", normalized_name="supplier b"))
        db.commit()

    with SessionLocal() as db:
        set_tenant_context(db, tenant_a)
        visible = int(db.scalar(select(func.count(Supplier.id))) or 0)
        if visible != 1:
            raise RuntimeError(f"RLS leaked suppliers: tenant A can see {visible}, expected 1")
        hidden = db.get(Supplier, supplier_b)
        if hidden is not None:
            raise RuntimeError("RLS allowed tenant A to read tenant B supplier")

        db.add(
            Document(
                tenant_id=tenant_a,
                supplier_id=supplier_b,
                document_type="invoice",
                number="CROSS-1",
                source_filename="cross.json",
                storage_path="smoke/cross.json",
                file_hash="b" * 64,
                parse_status="parsed",
                confidence=1.0,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise RuntimeError("Cross-tenant supplier reference was accepted")

    print("PostgreSQL RLS and tenant-reference smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
