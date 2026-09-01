"""add document evidence snapshots

Revision ID: a62d4b91c7e3
Revises: f31b0d7c6a52
Create Date: 2026-09-01 04:31:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a62d4b91c7e3"
down_revision: Union[str, Sequence[str], None] = "f31b0d7c6a52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "document_evidence_snapshots"
_TENANT_TRIGGER = "trg_tt_tenant_document_evidence_snapshots_document_id"
_POLICY = "tt_tenant_isolation_document_evidence_snapshots"


def _enable_postgres_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    predicate = "tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))"
    op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{_TENANT_TRIGGER}" ON "{_TABLE}"'))
    op.execute(
        sa.text(
            f'CREATE TRIGGER "{_TENANT_TRIGGER}" BEFORE INSERT OR UPDATE OF tenant_id, document_id ON "{_TABLE}" '
            "FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('documents', 'document_id')"
        )
    )
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_POLICY}" ON "{_TABLE}"'))
    op.execute(sa.text(f'CREATE POLICY "{_POLICY}" ON "{_TABLE}" USING ({predicate}) WITH CHECK ({predicate})'))


def _disable_postgres_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_POLICY}" ON "{_TABLE}"'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" NO FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" DISABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{_TENANT_TRIGGER}" ON "{_TABLE}"'))


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(op.f("ix_document_evidence_snapshots_tenant_id"), _TABLE, ["tenant_id"], unique=False)
    _enable_postgres_guards()


def downgrade() -> None:
    _disable_postgres_guards()
    op.drop_index(op.f("ix_document_evidence_snapshots_tenant_id"), table_name=_TABLE)
    op.drop_table(_TABLE)
