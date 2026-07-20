"""harden sessions, audit ordering, and monetary precision

Revision ID: b10a7c31f9d2
Revises: 9b3f17a42d91
Create Date: 2026-07-19 18:00:00.000000
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

revision: str = "b10a7c31f9d2"
down_revision: Union[str, Sequence[str], None] = "9b3f17a42d91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp(value: datetime) -> str:
    return value.replace(tzinfo=None).isoformat(timespec="microseconds")


def _digest(row: sa.RowMapping, previous_hash: str | None, sequence_no: int | None) -> str:
    payload = {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "actor_id": row["actor_id"],
        "action": row["action"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "payload_json": row["payload_json"],
        "previous_hash": previous_hash,
        "created_at": _timestamp(row["created_at"]),
    }
    if sequence_no is not None:
        payload["sequence_no"] = sequence_no
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _rebuild_audit(*, include_sequence: bool) -> None:
    # Offline SQL is generated only as a fresh-schema reference artifact. A populated
    # database must run this migration online so hashes can be rebuilt from real rows.
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    tenants = [row[0] for row in bind.execute(sa.text("SELECT id FROM tenants ORDER BY id"))]
    for tenant_id in tenants:
        rows = list(
            bind.execute(
                sa.text(
                    "SELECT id, tenant_id, actor_id, action, entity_type, entity_id, payload_json, created_at "
                    "FROM audit_events WHERE tenant_id = :tenant_id ORDER BY created_at, id"
                ),
                {"tenant_id": tenant_id},
            ).mappings()
        )
        previous_hash = None
        for sequence_no, row in enumerate(rows, start=1):
            event_hash = _digest(row, previous_hash, sequence_no if include_sequence else None)
            if include_sequence:
                bind.execute(
                    sa.text(
                        "UPDATE audit_events SET sequence_no = :sequence_no, previous_hash = :previous_hash, "
                        "event_hash = :event_hash WHERE id = :id"
                    ),
                    {
                        "sequence_no": sequence_no,
                        "previous_hash": previous_hash,
                        "event_hash": event_hash,
                        "id": row["id"],
                    },
                )
            else:
                bind.execute(
                    sa.text(
                        "UPDATE audit_events SET previous_hash = :previous_hash, event_hash = :event_hash WHERE id = :id"
                    ),
                    {"previous_hash": previous_hash, "event_hash": event_hash, "id": row["id"]},
                )
            previous_hash = event_hash
        if include_sequence:
            bind.execute(
                sa.text("UPDATE tenants SET audit_sequence = :value WHERE id = :tenant_id"),
                {"value": len(rows), "tenant_id": tenant_id},
            )


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("security_version", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("audit_sequence", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_sessions_tenant_id"), "auth_sessions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_index("ix_auth_session_tenant_active", "auth_sessions", ["tenant_id", "active"], unique=False)
    op.create_index("ix_auth_session_user_active", "auth_sessions", ["user_id", "active"], unique=False)

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("sequence_no", sa.Integer(), nullable=True))
    _rebuild_audit(include_sequence=True)
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("sequence_no", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_audit_tenant_sequence", ["tenant_id", "sequence_no"])

    with op.batch_alter_table("document_lines") as batch:
        batch.add_column(sa.Column("unit_of_measure", sa.String(length=40), nullable=True))
        batch.add_column(
            sa.Column(
                "price_base_quantity",
                sa.Numeric(precision=24, scale=8),
                nullable=False,
                server_default="1",
            )
        )
        batch.alter_column(
            "quantity",
            existing_type=sa.Numeric(precision=18, scale=4),
            type_=sa.Numeric(precision=24, scale=8),
            existing_nullable=False,
        )
        batch.alter_column(
            "unit_price",
            existing_type=sa.Numeric(precision=18, scale=6),
            type_=sa.Numeric(precision=24, scale=10),
            existing_nullable=False,
        )
        batch.alter_column(
            "discount_rate",
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=12, scale=8),
            existing_nullable=False,
        )
        batch.alter_column(
            "tax_rate",
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=12, scale=8),
            existing_nullable=False,
        )
        batch.alter_column(
            "line_total",
            existing_type=sa.Numeric(precision=18, scale=2),
            type_=sa.Numeric(precision=24, scale=8),
            existing_nullable=False,
        )


def downgrade() -> None:
    _rebuild_audit(include_sequence=False)

    with op.batch_alter_table("document_lines") as batch:
        batch.alter_column(
            "line_total",
            existing_type=sa.Numeric(precision=24, scale=8),
            type_=sa.Numeric(precision=18, scale=2),
            existing_nullable=False,
        )
        batch.alter_column(
            "tax_rate",
            existing_type=sa.Numeric(precision=12, scale=8),
            type_=sa.Float(),
            existing_nullable=False,
        )
        batch.alter_column(
            "discount_rate",
            existing_type=sa.Numeric(precision=12, scale=8),
            type_=sa.Float(),
            existing_nullable=False,
        )
        batch.alter_column(
            "unit_price",
            existing_type=sa.Numeric(precision=24, scale=10),
            type_=sa.Numeric(precision=18, scale=6),
            existing_nullable=False,
        )
        batch.alter_column(
            "quantity",
            existing_type=sa.Numeric(precision=24, scale=8),
            type_=sa.Numeric(precision=18, scale=4),
            existing_nullable=False,
        )
        batch.drop_column("price_base_quantity")
        batch.drop_column("unit_of_measure")

    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("uq_audit_tenant_sequence", type_="unique")
        batch.drop_column("sequence_no")

    op.drop_index("ix_auth_session_user_active", table_name="auth_sessions")
    op.drop_index("ix_auth_session_tenant_active", table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_tenant_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")

    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("audit_sequence")
        batch.drop_column("security_version")
