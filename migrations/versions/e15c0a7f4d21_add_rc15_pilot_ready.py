"""add RC15 pilot-ready workflow tables

Revision ID: e15c0a7f4d21
Revises: d42a0f61be90
Create Date: 2026-08-27 20:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e15c0a7f4d21"
down_revision: Union[str, Sequence[str], None] = "d42a0f61be90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = (
    "rc15_intake_records",
    "rc15_case_economic_assessments",
    "rc15_company_profile_versions",
    "rc15_practices",
    "rc15_pilot_workspaces",
    "rc15_pilot_cases",
)

TENANT_REFERENCES = (
    ("rc15_intake_records", "classified_by", "users"),
    ("rc15_case_economic_assessments", "case_id", "discrepancy_cases"),
    ("rc15_case_economic_assessments", "assessed_by", "users"),
    ("rc15_company_profile_versions", "created_by", "users"),
    ("rc15_practices", "chain_id", "operation_chains"),
    ("rc15_practices", "profile_version_id", "rc15_company_profile_versions"),
    ("rc15_practices", "created_by", "users"),
    ("rc15_pilot_workspaces", "profile_version_id", "rc15_company_profile_versions"),
    ("rc15_pilot_workspaces", "created_by", "users"),
    ("rc15_pilot_cases", "pilot_id", "rc15_pilot_workspaces"),
    ("rc15_pilot_cases", "practice_id", "rc15_practices"),
)


def _trigger_name(table: str, column: str) -> str:
    return f"trg_tt_tenant_{table}_{column}"[:63]


def _enable_postgres_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    predicate = "tenant_id::text = (SELECT NULLIF(current_setting('app.current_tenant', true), ''))"
    for table, column, parent in TENANT_REFERENCES:
        name = _trigger_name(table, column)
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{name}" ON "{table}"'))
        op.execute(
            sa.text(
                f'CREATE TRIGGER "{name}" BEFORE INSERT OR UPDATE OF tenant_id, "{column}" ON "{table}" '
                f"FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('{parent}', '{column}')"
            )
        )
    for table in RLS_TABLES:
        policy = f"tt_tenant_isolation_{table}"[:63]
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
        op.execute(sa.text(f'CREATE POLICY "{policy}" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})'))


def _disable_postgres_guards() -> None:
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


def upgrade() -> None:
    op.create_table(
        "rc15_intake_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("phase", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("automatic", sa.Boolean(), nullable=False),
        sa.Column("classified_by", sa.String(length=36), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("subject_type IN ('document', 'job')", name="ck_rc15_intake_subject_type"),
        sa.CheckConstraint(
            "state IN ('acquired', 'review_required', 'not_acquired', 'blocked', 'out_of_scope')",
            name="ck_rc15_intake_state",
        ),
        sa.CheckConstraint(
            "category IN ('ok', 'degraded', 'hostile', 'out_of_scope', 'parser_limit', 'operator_input', 'security_block')",
            name="ck_rc15_intake_category",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["classified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "subject_type", "subject_id", name="uq_rc15_intake_subject"),
    )
    op.create_index(op.f("ix_rc15_intake_records_tenant_id"), "rc15_intake_records", ["tenant_id"], unique=False)
    op.create_index("ix_rc15_intake_tenant_updated", "rc15_intake_records", ["tenant_id", "updated_at"], unique=False)

    op.create_table(
        "rc15_case_economic_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("potential_exposure", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("confirmed_loss", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("assessed_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("potential_exposure IS NULL OR potential_exposure >= 0", name="ck_rc15_potential_nonnegative"),
        sa.CheckConstraint("confirmed_loss IS NULL OR confirmed_loss >= 0", name="ck_rc15_loss_nonnegative"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["discrepancy_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "case_id", name="uq_rc15_case_economic_case"),
    )
    op.create_index(op.f("ix_rc15_case_economic_assessments_tenant_id"), "rc15_case_economic_assessments", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_rc15_case_economic_assessments_case_id"), "rc15_case_economic_assessments", ["case_id"], unique=False)

    op.create_table(
        "rc15_company_profile_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "version", name="uq_rc15_company_profile_version"),
        sa.UniqueConstraint("tenant_id", "config_hash", name="uq_rc15_company_profile_hash"),
    )
    op.create_index(op.f("ix_rc15_company_profile_versions_tenant_id"), "rc15_company_profile_versions", ["tenant_id"], unique=False)
    op.create_index("ix_rc15_company_profile_active", "rc15_company_profile_versions", ["tenant_id", "active"], unique=False)

    op.create_table(
        "rc15_practices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("chain_id", sa.String(length=36), nullable=True),
        sa.Column("profile_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("retention_end", sa.Date(), nullable=True),
        sa.Column("tombstone_hash", sa.String(length=64), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_rc15_practice_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chain_id"], ["operation_chains.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_version_id"], ["rc15_company_profile_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "chain_id", name="uq_rc15_practice_chain"),
    )
    op.create_index(op.f("ix_rc15_practices_tenant_id"), "rc15_practices", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_rc15_practices_chain_id"), "rc15_practices", ["chain_id"], unique=False)
    op.create_index("ix_rc15_practice_tenant_status", "rc15_practices", ["tenant_id", "status"], unique=False)

    op.create_table(
        "rc15_pilot_workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("authorization_reference", sa.String(length=240), nullable=False),
        sa.Column("reviewer_primary", sa.String(length=120), nullable=False),
        sa.Column("reviewer_secondary", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("retention_end", sa.Date(), nullable=True),
        sa.Column("profile_version_id", sa.String(length=36), nullable=True),
        sa.Column("ground_truth_hash", sa.String(length=64), nullable=True),
        sa.Column("engine_version", sa.String(length=80), nullable=True),
        sa.Column("freeze_manifest_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'frozen', 'running', 'completed', 'archived')",
            name="ck_rc15_pilot_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_version_id"], ["rc15_company_profile_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_rc15_pilot_version"),
    )
    op.create_index(op.f("ix_rc15_pilot_workspaces_tenant_id"), "rc15_pilot_workspaces", ["tenant_id"], unique=False)
    op.create_index("ix_rc15_pilot_tenant_status", "rc15_pilot_workspaces", ["tenant_id", "status"], unique=False)

    op.create_table(
        "rc15_pilot_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("pilot_id", sa.String(length=36), nullable=False),
        sa.Column("practice_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_primary_json", sa.Text(), nullable=False),
        sa.Column("reviewer_secondary_json", sa.Text(), nullable=False),
        sa.Column("adjudicated_json", sa.Text(), nullable=False),
        sa.Column("manual_seconds", sa.Float(), nullable=True),
        sa.Column("assisted_seconds", sa.Float(), nullable=True),
        sa.Column("user_score", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("manual_seconds IS NULL OR manual_seconds > 0", name="ck_rc15_manual_seconds"),
        sa.CheckConstraint("assisted_seconds IS NULL OR assisted_seconds > 0", name="ck_rc15_assisted_seconds"),
        sa.CheckConstraint("user_score IS NULL OR (user_score >= 1 AND user_score <= 5)", name="ck_rc15_user_score"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pilot_id"], ["rc15_pilot_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["practice_id"], ["rc15_practices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "pilot_id", "practice_id", name="uq_rc15_pilot_practice"),
    )
    op.create_index(op.f("ix_rc15_pilot_cases_tenant_id"), "rc15_pilot_cases", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_rc15_pilot_cases_pilot_id"), "rc15_pilot_cases", ["pilot_id"], unique=False)
    op.create_index(op.f("ix_rc15_pilot_cases_practice_id"), "rc15_pilot_cases", ["practice_id"], unique=False)
    op.create_index("ix_rc15_pilot_case_pilot", "rc15_pilot_cases", ["tenant_id", "pilot_id"], unique=False)

    _enable_postgres_guards()


def downgrade() -> None:
    _disable_postgres_guards()
    op.drop_index("ix_rc15_pilot_case_pilot", table_name="rc15_pilot_cases")
    op.drop_index(op.f("ix_rc15_pilot_cases_practice_id"), table_name="rc15_pilot_cases")
    op.drop_index(op.f("ix_rc15_pilot_cases_pilot_id"), table_name="rc15_pilot_cases")
    op.drop_index(op.f("ix_rc15_pilot_cases_tenant_id"), table_name="rc15_pilot_cases")
    op.drop_table("rc15_pilot_cases")
    op.drop_index("ix_rc15_pilot_tenant_status", table_name="rc15_pilot_workspaces")
    op.drop_index(op.f("ix_rc15_pilot_workspaces_tenant_id"), table_name="rc15_pilot_workspaces")
    op.drop_table("rc15_pilot_workspaces")
    op.drop_index("ix_rc15_practice_tenant_status", table_name="rc15_practices")
    op.drop_index(op.f("ix_rc15_practices_chain_id"), table_name="rc15_practices")
    op.drop_index(op.f("ix_rc15_practices_tenant_id"), table_name="rc15_practices")
    op.drop_table("rc15_practices")
    op.drop_index("ix_rc15_company_profile_active", table_name="rc15_company_profile_versions")
    op.drop_index(op.f("ix_rc15_company_profile_versions_tenant_id"), table_name="rc15_company_profile_versions")
    op.drop_table("rc15_company_profile_versions")
    op.drop_index(op.f("ix_rc15_case_economic_assessments_case_id"), table_name="rc15_case_economic_assessments")
    op.drop_index(op.f("ix_rc15_case_economic_assessments_tenant_id"), table_name="rc15_case_economic_assessments")
    op.drop_table("rc15_case_economic_assessments")
    op.drop_index("ix_rc15_intake_tenant_updated", table_name="rc15_intake_records")
    op.drop_index(op.f("ix_rc15_intake_records_tenant_id"), table_name="rc15_intake_records")
    op.drop_table("rc15_intake_records")
