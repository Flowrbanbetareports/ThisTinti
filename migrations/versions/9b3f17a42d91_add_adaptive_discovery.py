"""add adaptive activity discovery and rule proposals

Revision ID: 9b3f17a42d91
Revises: 4c720e60d5f2
Create Date: 2026-07-19 15:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9b3f17a42d91"
down_revision: Union[str, Sequence[str], None] = "4c720e60d5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("activity_type", sa.String(length=120), nullable=False),
        sa.Column("activity_label", sa.String(length=180), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("field_profile_json", sa.Text(), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("human_confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by", sa.String(length=36), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('learning', 'ready', 'needs_confirmation')",
            name="ck_activity_profile_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_activity_profile_tenant"),
    )
    op.create_index(op.f("ix_activity_profiles_tenant_id"), "activity_profiles", ["tenant_id"], unique=False)

    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("activity_type", sa.String(length=120), nullable=True),
        sa.Column("activity_confidence", sa.Float(), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("proposed_rules", sa.Integer(), nullable=False),
        sa.Column("auto_activated_rules", sa.Integer(), nullable=False),
        sa.Column("uncertain_rules", sa.Integer(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_discovery_run_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_run_tenant_created", "discovery_runs", ["tenant_id", "created_at"], unique=False)
    op.create_index(op.f("ix_discovery_runs_tenant_id"), "discovery_runs", ["tenant_id"], unique=False)

    op.create_table(
        "rule_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("rule_code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("confirmed_by", sa.String(length=36), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('auto_active', 'needs_confirmation', 'confirmed', 'rejected', 'inactive')",
            name="ck_rule_proposal_status",
        ),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "rule_code", name="uq_rule_proposal_tenant_code"),
    )
    op.create_index(op.f("ix_rule_proposals_tenant_id"), "rule_proposals", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rule_proposals_tenant_id"), table_name="rule_proposals")
    op.drop_table("rule_proposals")
    op.drop_index(op.f("ix_discovery_runs_tenant_id"), table_name="discovery_runs")
    op.drop_index("ix_discovery_run_tenant_created", table_name="discovery_runs")
    op.drop_table("discovery_runs")
    op.drop_index(op.f("ix_activity_profiles_tenant_id"), table_name="activity_profiles")
    op.drop_table("activity_profiles")
