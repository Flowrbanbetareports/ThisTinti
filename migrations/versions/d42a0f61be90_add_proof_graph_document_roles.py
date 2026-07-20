"""add proposal and payment roles for proof graph intelligence

Revision ID: d42a0f61be90
Revises: c21d9e4a7b63
Create Date: 2026-07-20 01:15:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d42a0f61be90"
down_revision: Union[str, Sequence[str], None] = "c21d9e4a7b63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DOCUMENT_TYPES = "'proposal', 'order', 'confirmation', 'delivery', 'invoice', 'payment', 'return', 'credit_note'"
OLD_DOCUMENT_TYPES = "'order', 'confirmation', 'delivery', 'invoice', 'return', 'credit_note'"


def _postgres_tenant_trigger(table: str, column: str, parent: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    name = f"trg_tt_tenant_{table}_{column}"[:63]
    op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{name}" ON "{table}"'))
    op.execute(
        sa.text(
            f'CREATE TRIGGER "{name}" BEFORE INSERT OR UPDATE OF tenant_id, "{column}" ON "{table}" '
            f"FOR EACH ROW EXECUTE FUNCTION thistinti_assert_tenant_reference('{parent}', '{column}')"
        )
    )


def upgrade() -> None:
    with op.batch_alter_table("validation_datasets") as batch:
        batch.add_column(sa.Column("evidence_level", sa.String(length=30), nullable=False, server_default="synthetic"))
        batch.add_column(sa.Column("automation_eligible", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_check_constraint(
            "ck_validation_dataset_evidence_level",
            "evidence_level IN ('synthetic', 'anonymized_pilot', 'production')",
        )
        batch.create_check_constraint(
            "ck_validation_dataset_automation_evidence",
            "NOT automation_eligible OR evidence_level IN ('anonymized_pilot', 'production')",
        )

    with op.batch_alter_table("validation_runs") as batch:
        batch.add_column(sa.Column("automation_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("automation_approved_by", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("automation_approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("automation_approval_note", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_validation_runs_automation_approved_by",
            "users",
            ["automation_approved_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_check_constraint(
            "ck_validation_run_approval_evidence",
            "NOT automation_approved OR "
            "(automation_approved_by IS NOT NULL AND automation_approved_at IS NOT NULL "
            "AND automation_approval_note IS NOT NULL)",
        )

    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("ck_document_type", type_="check")
        batch.create_check_constraint("ck_document_type", f"document_type IN ({DOCUMENT_TYPES})")

    with op.batch_alter_table("chain_documents") as batch:
        batch.drop_constraint("ck_chain_document_role", type_="check")
        batch.create_check_constraint("ck_chain_document_role", f"role IN ({DOCUMENT_TYPES})")

    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_constraint("ck_processing_job_type", type_="check")
        batch.create_check_constraint(
            "ck_processing_job_type",
            "job_type IN ('ingest_document', 'ingest_batch', 'reprocess_document', 'reanalyze_tenant', 'red_team_tenant')",
        )

    with op.batch_alter_table("operation_chains") as batch:
        batch.add_column(sa.Column("proposal_document_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("payment_document_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_operation_chains_proposal_document",
            "documents",
            ["proposal_document_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_operation_chains_payment_document",
            "documents",
            ["payment_document_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _postgres_tenant_trigger("operation_chains", "proposal_document_id", "documents")
    _postgres_tenant_trigger("operation_chains", "payment_document_id", "documents")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for column in ("payment_document_id", "proposal_document_id"):
            name = f"trg_tt_tenant_operation_chains_{column}"[:63]
            op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{name}" ON "operation_chains"'))

    # Downgrade is intentionally blocked if new document roles are still present.
    payment_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM documents WHERE document_type IN ('proposal', 'payment')")
    ).scalar_one()
    link_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM chain_documents WHERE role IN ('proposal', 'payment')")
    ).scalar_one()
    red_team_job_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM processing_jobs WHERE job_type = 'red_team_tenant'")
    ).scalar_one()
    if payment_count or link_count or red_team_job_count:
        raise RuntimeError(
            "Remove or convert proposal/payment documents and red-team jobs before downgrading below 3.2"
        )

    with op.batch_alter_table("validation_runs") as batch:
        batch.drop_constraint("ck_validation_run_approval_evidence", type_="check")
        batch.drop_constraint("fk_validation_runs_automation_approved_by", type_="foreignkey")
        batch.drop_column("automation_approval_note")
        batch.drop_column("automation_approved_at")
        batch.drop_column("automation_approved_by")
        batch.drop_column("automation_approved")

    with op.batch_alter_table("validation_datasets") as batch:
        batch.drop_constraint("ck_validation_dataset_automation_evidence", type_="check")
        batch.drop_constraint("ck_validation_dataset_evidence_level", type_="check")
        batch.drop_column("automation_eligible")
        batch.drop_column("evidence_level")

    with op.batch_alter_table("operation_chains") as batch:
        batch.drop_constraint("fk_operation_chains_payment_document", type_="foreignkey")
        batch.drop_constraint("fk_operation_chains_proposal_document", type_="foreignkey")
        batch.drop_column("payment_document_id")
        batch.drop_column("proposal_document_id")

    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_constraint("ck_processing_job_type", type_="check")
        batch.create_check_constraint(
            "ck_processing_job_type",
            "job_type IN ('ingest_document', 'ingest_batch', 'reprocess_document', 'reanalyze_tenant')",
        )

    with op.batch_alter_table("chain_documents") as batch:
        batch.drop_constraint("ck_chain_document_role", type_="check")
        batch.create_check_constraint("ck_chain_document_role", f"role IN ({OLD_DOCUMENT_TYPES})")

    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("ck_document_type", type_="check")
        batch.create_check_constraint("ck_document_type", f"document_type IN ({OLD_DOCUMENT_TYPES})")
