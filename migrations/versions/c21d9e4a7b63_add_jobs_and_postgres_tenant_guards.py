"""add persistent jobs and PostgreSQL tenant guards

Revision ID: c21d9e4a7b63
Revises: b10a7c31f9d2
Create Date: 2026-07-19 20:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c21d9e4a7b63"
down_revision: Union[str, Sequence[str], None] = "b10a7c31f9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = (
    "suppliers",
    "supplier_aliases",
    "item_aliases",
    "documents",
    "document_lines",
    "operation_chains",
    "chain_documents",
    "discrepancy_cases",
    "evidence_links",
    "review_decisions",
    "validation_datasets",
    "validation_runs",
    "activity_profiles",
    "discovery_runs",
    "rule_proposals",
    "audit_events",
)

TENANT_REFERENCES = (
    ("auth_sessions", "user_id", "users"),
    ("api_credentials", "created_by", "users"),
    ("processing_jobs", "created_by", "users"),
    ("processing_jobs", "created_by_api_credential", "api_credentials"),
    ("supplier_aliases", "supplier_id", "suppliers"),
    ("item_aliases", "supplier_id", "suppliers"),
    ("documents", "supplier_id", "suppliers"),
    ("document_lines", "document_id", "documents"),
    ("operation_chains", "supplier_id", "suppliers"),
    ("operation_chains", "order_document_id", "documents"),
    ("operation_chains", "confirmation_document_id", "documents"),
    ("operation_chains", "delivery_document_id", "documents"),
    ("operation_chains", "invoice_document_id", "documents"),
    ("operation_chains", "return_document_id", "documents"),
    ("operation_chains", "credit_note_document_id", "documents"),
    ("chain_documents", "chain_id", "operation_chains"),
    ("chain_documents", "document_id", "documents"),
    ("discrepancy_cases", "chain_id", "operation_chains"),
    ("evidence_links", "case_id", "discrepancy_cases"),
    ("evidence_links", "document_id", "documents"),
    ("evidence_links", "document_line_id", "document_lines"),
    ("review_decisions", "case_id", "discrepancy_cases"),
    ("review_decisions", "user_id", "users"),
    ("validation_datasets", "created_by", "users"),
    ("validation_runs", "dataset_id", "validation_datasets"),
    ("validation_runs", "created_by", "users"),
    ("activity_profiles", "confirmed_by", "users"),
    ("discovery_runs", "created_by", "users"),
    ("rule_proposals", "confirmed_by", "users"),
)


def _trigger_name(table: str, column: str) -> str:
    return f"trg_tt_tenant_{table}_{column}"[:63]


def _enable_postgres_tenant_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION thistinti_assert_tenant_reference()
        RETURNS trigger AS $$
        DECLARE
            reference_id text;
            reference_tenant text;
        BEGIN
            reference_id := to_jsonb(NEW) ->> TG_ARGV[1];
            IF reference_id IS NULL OR reference_id = '' THEN
                RETURN NEW;
            END IF;

            EXECUTE format('SELECT tenant_id::text FROM %I WHERE id::text = $1', TG_ARGV[0])
            INTO reference_tenant
            USING reference_id;

            IF reference_tenant IS NULL THEN
                RAISE EXCEPTION 'Referenced row %.%=% does not exist', TG_ARGV[0], TG_ARGV[1], reference_id
                    USING ERRCODE = 'foreign_key_violation';
            END IF;
            IF reference_tenant <> NEW.tenant_id::text THEN
                RAISE EXCEPTION 'Cross-tenant reference rejected on %.%: row tenant %, referenced tenant %',
                    TG_TABLE_NAME, TG_ARGV[1], NEW.tenant_id, reference_tenant
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table, column, parent in TENANT_REFERENCES:
        name = _trigger_name(table, column)
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{name}" ON "{table}"'))
        op.execute(
            sa.text(
                f'CREATE TRIGGER "{name}" BEFORE INSERT OR UPDATE OF tenant_id, "{column}" ON "{table}" '
                f"FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('{parent}', '{column}')"
            )
        )

    predicate = "tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))"
    for table in RLS_TABLES:
        policy = f"tt_tenant_isolation_{table}"[:63]
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
        op.execute(sa.text(f'CREATE POLICY "{policy}" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})'))


def _disable_postgres_tenant_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in reversed(RLS_TABLES):
        policy = f"tt_tenant_isolation_{table}"[:63]
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    for table, column, _parent in reversed(TENANT_REFERENCES):
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{_trigger_name(table, column)}" ON "{table}"'))
    op.execute("DROP FUNCTION IF EXISTS thistinti_assert_tenant_reference()")


def upgrade() -> None:
    op.create_table(
        "api_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="viewer"),
        sa.Column("scopes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('reviewer', 'viewer')", name="ck_api_credential_role"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_credentials_tenant_id"), "api_credentials", ["tenant_id"], unique=False)
    op.create_index("ix_api_credential_tenant_active", "api_credentials", ["tenant_id", "active"], unique=False)

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_by_api_credential", sa.String(length=36), nullable=True),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=180), nullable=True),
        sa.Column("input_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "job_type IN ('ingest_document', 'ingest_batch', 'reprocess_document', 'reanalyze_tenant')",
            name="ck_processing_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_processing_job_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_api_credential"], ["api_credentials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_job_tenant_idempotency"),
    )
    op.create_index(op.f("ix_processing_jobs_tenant_id"), "processing_jobs", ["tenant_id"], unique=False)
    op.create_index("ix_job_claim", "processing_jobs", ["status", "available_at", "created_at"], unique=False)
    op.create_index("ix_job_tenant_created", "processing_jobs", ["tenant_id", "created_at"], unique=False)

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=120), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index(op.f("ix_worker_heartbeats_last_seen_at"), "worker_heartbeats", ["last_seen_at"], unique=False)
    op.create_table(
        "rate_limit_counters",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(
        op.f("ix_rate_limit_counters_expires_at"),
        "rate_limit_counters",
        ["expires_at"],
        unique=False,
    )
    _enable_postgres_tenant_guards()


def downgrade() -> None:
    _disable_postgres_tenant_guards()
    op.drop_index(op.f("ix_rate_limit_counters_expires_at"), table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
    op.drop_index(op.f("ix_worker_heartbeats_last_seen_at"), table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
    op.drop_index("ix_job_tenant_created", table_name="processing_jobs")
    op.drop_index("ix_job_claim", table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_tenant_id"), table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_api_credential_tenant_active", table_name="api_credentials")
    op.drop_index(op.f("ix_api_credentials_tenant_id"), table_name="api_credentials")
    op.drop_table("api_credentials")
