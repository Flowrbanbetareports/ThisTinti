"""add provenance persistence v0

Revision ID: f31b0d7c6a52
Revises: e15c0a7f4d21
Create Date: 2026-08-28 03:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f31b0d7c6a52"
down_revision: Union[str, Sequence[str], None] = "e15c0a7f4d21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = (
    "provenance_derivations",
    "provenance_origins",
    "provenance_facts",
    "provenance_derivation_inputs",
    "provenance_findings",
    "provenance_finding_facts",
    "provenance_judgments",
)

TENANT_REFERENCES = (
    ("provenance_origins", "document_id", "documents"),
    ("provenance_origins", "actor_user_id", "users"),
    ("provenance_origins", "derivation_id", "provenance_derivations"),
    ("provenance_facts", "origin_id", "provenance_origins"),
    ("provenance_facts", "supersedes_fact_id", "provenance_facts"),
    ("provenance_derivation_inputs", "derivation_id", "provenance_derivations"),
    ("provenance_derivation_inputs", "fact_id", "provenance_facts"),
    ("provenance_findings", "case_id", "discrepancy_cases"),
    ("provenance_findings", "supersedes_finding_id", "provenance_findings"),
    ("provenance_finding_facts", "finding_id", "provenance_findings"),
    ("provenance_finding_facts", "fact_id", "provenance_facts"),
    ("provenance_judgments", "finding_id", "provenance_findings"),
    ("provenance_judgments", "review_decision_id", "review_decisions"),
    ("provenance_judgments", "reviewer_user_id", "users"),
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
        "provenance_derivations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("transformation_id", sa.String(length=240), nullable=False),
        sa.Column("engine_id", sa.String(length=160), nullable=False),
        sa.Column("engine_version", sa.String(length=120), nullable=False),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_provenance_derivations_tenant_id"), "provenance_derivations", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_prov_derivation_tenant_created", "provenance_derivations", ["tenant_id", "created_at"], unique=False
    )

    op.create_table(
        "provenance_origins",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("origin_type", sa.String(length=40), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("source_availability", sa.String(length=40), nullable=True),
        sa.Column("locator_status", sa.String(length=30), nullable=True),
        sa.Column("locator_type", sa.String(length=40), nullable=True),
        sa.Column("locator_json", sa.Text(), nullable=True),
        sa.Column("actor_ref", sa.String(length=240), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("asserted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engine_id", sa.String(length=160), nullable=True),
        sa.Column("engine_version", sa.String(length=120), nullable=True),
        sa.Column("configuration_hash", sa.String(length=64), nullable=True),
        sa.Column("derivation_id", sa.String(length=36), nullable=True),
        sa.Column("legacy_marker", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "origin_type IN ('DOCUMENT_EVIDENCE', 'HUMAN_ASSERTION', 'MASTER_DATA_IMPORT', "
            "'SYSTEM_OBSERVATION', 'DETERMINISTIC_DERIVATION', 'LEGACY_ORIGIN_UNKNOWN')",
            name="ck_prov_origin_type",
        ),
        sa.CheckConstraint(
            "source_availability IS NULL OR source_availability IN "
            "('available', 'deleted_by_retention', 'not_stored', 'access_denied', 'external_unavailable', 'legacy_unknown')",
            name="ck_prov_source_availability",
        ),
        sa.CheckConstraint(
            "locator_status IS NULL OR locator_status IN ('present', 'missing', 'not_applicable')",
            name="ck_prov_locator_status",
        ),
        sa.CheckConstraint(
            "locator_type IS NULL OR locator_type IN "
            "('PDF_PAGE_BOX', 'IMAGE_BOX', 'TEXT_RANGE', 'CSV_CELL', 'XLSX_CELL', 'JSON_POINTER', 'XPATH')",
            name="ck_prov_locator_type",
        ),
        sa.CheckConstraint(
            "(locator_status IS NULL) OR "
            "(locator_status = 'present' AND locator_type IS NOT NULL AND locator_json IS NOT NULL) OR "
            "(locator_status IN ('missing', 'not_applicable') AND locator_type IS NULL)",
            name="ck_prov_locator_shape",
        ),
        sa.CheckConstraint(
            "origin_type != 'DOCUMENT_EVIDENCE' OR "
            "(source_ref IS NOT NULL AND source_availability IS NOT NULL AND locator_status IS NOT NULL)",
            name="ck_prov_document_origin",
        ),
        sa.CheckConstraint(
            "origin_type != 'HUMAN_ASSERTION' OR "
            "(actor_ref IS NOT NULL AND asserted_at IS NOT NULL AND reason IS NOT NULL)",
            name="ck_prov_human_origin",
        ),
        sa.CheckConstraint(
            "origin_type != 'MASTER_DATA_IMPORT' OR (source_ref IS NOT NULL AND imported_at IS NOT NULL)",
            name="ck_prov_master_origin",
        ),
        sa.CheckConstraint(
            "origin_type != 'SYSTEM_OBSERVATION' OR "
            "(engine_id IS NOT NULL AND engine_version IS NOT NULL AND observed_at IS NOT NULL)",
            name="ck_prov_system_origin",
        ),
        sa.CheckConstraint(
            "origin_type != 'DETERMINISTIC_DERIVATION' OR derivation_id IS NOT NULL",
            name="ck_prov_derivation_origin",
        ),
        sa.CheckConstraint(
            "origin_type != 'LEGACY_ORIGIN_UNKNOWN' OR legacy_marker IS NOT NULL",
            name="ck_prov_legacy_origin",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["derivation_id"], ["provenance_derivations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provenance_origins_tenant_id"), "provenance_origins", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_provenance_origins_derivation_id"), "provenance_origins", ["derivation_id"], unique=False)
    op.create_index("ix_prov_origin_tenant_type", "provenance_origins", ["tenant_id", "origin_type"], unique=False)

    op.create_table(
        "provenance_facts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("fact_key", sa.String(length=300), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fact_type", sa.String(length=160), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("origin_id", sa.String(length=36), nullable=False),
        sa.Column("supersedes_fact_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_prov_fact_version_positive"),
        sa.CheckConstraint(
            "(version = 1 AND supersedes_fact_id IS NULL) OR (version > 1 AND supersedes_fact_id IS NOT NULL)",
            name="ck_prov_fact_supersession",
        ),
        sa.CheckConstraint("supersedes_fact_id IS NULL OR supersedes_fact_id != id", name="ck_prov_fact_not_self"),
        sa.ForeignKeyConstraint(["origin_id"], ["provenance_origins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_fact_id"], ["provenance_facts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "fact_key", "version", name="uq_prov_fact_version"),
    )
    op.create_index(op.f("ix_provenance_facts_tenant_id"), "provenance_facts", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_provenance_facts_origin_id"), "provenance_facts", ["origin_id"], unique=False)
    op.create_index(
        op.f("ix_provenance_facts_supersedes_fact_id"), "provenance_facts", ["supersedes_fact_id"], unique=False
    )
    op.create_index("ix_prov_fact_tenant_key", "provenance_facts", ["tenant_id", "fact_key"], unique=False)

    op.create_table(
        "provenance_derivation_inputs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("derivation_id", sa.String(length=36), nullable=False),
        sa.Column("fact_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_prov_derivation_position_positive"),
        sa.ForeignKeyConstraint(["derivation_id"], ["provenance_derivations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fact_id"], ["provenance_facts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "derivation_id", "fact_id", name="uq_prov_derivation_fact"),
        sa.UniqueConstraint("tenant_id", "derivation_id", "position", name="uq_prov_derivation_position"),
    )
    op.create_index(
        op.f("ix_provenance_derivation_inputs_tenant_id"), "provenance_derivation_inputs", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_provenance_derivation_inputs_derivation_id"),
        "provenance_derivation_inputs",
        ["derivation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provenance_derivation_inputs_fact_id"), "provenance_derivation_inputs", ["fact_id"], unique=False
    )

    op.create_table(
        "provenance_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.String(length=240), nullable=False),
        sa.Column("rule_version", sa.String(length=120), nullable=False),
        sa.Column("rule_configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("supersedes_finding_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_prov_finding_version_positive"),
        sa.CheckConstraint(
            "(version = 1 AND supersedes_finding_id IS NULL) OR "
            "(version > 1 AND supersedes_finding_id IS NOT NULL)",
            name="ck_prov_finding_supersession",
        ),
        sa.CheckConstraint(
            "supersedes_finding_id IS NULL OR supersedes_finding_id != id", name="ck_prov_finding_not_self"
        ),
        sa.ForeignKeyConstraint(["case_id"], ["discrepancy_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_finding_id"], ["provenance_findings.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "case_id", "version", name="uq_prov_finding_version"),
    )
    op.create_index(op.f("ix_provenance_findings_tenant_id"), "provenance_findings", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_provenance_findings_case_id"), "provenance_findings", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_provenance_findings_supersedes_finding_id"),
        "provenance_findings",
        ["supersedes_finding_id"],
        unique=False,
    )
    op.create_index("ix_prov_finding_tenant_case", "provenance_findings", ["tenant_id", "case_id"], unique=False)

    op.create_table(
        "provenance_finding_facts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("finding_id", sa.String(length=36), nullable=False),
        sa.Column("fact_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["fact_id"], ["provenance_facts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["finding_id"], ["provenance_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "finding_id", "fact_id", name="uq_prov_finding_fact"),
    )
    op.create_index(
        op.f("ix_provenance_finding_facts_tenant_id"), "provenance_finding_facts", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_provenance_finding_facts_finding_id"), "provenance_finding_facts", ["finding_id"], unique=False
    )
    op.create_index(
        op.f("ix_provenance_finding_facts_fact_id"), "provenance_finding_facts", ["fact_id"], unique=False
    )

    op.create_table(
        "provenance_judgments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("finding_id", sa.String(length=36), nullable=False),
        sa.Column("review_decision_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_ref", sa.String(length=240), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("previous_state", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('confirmed', 'dismissed', 'needs_review', 'resolved')", name="ck_prov_judgment_decision"
        ),
        sa.CheckConstraint(
            "previous_state IN ('open', 'needs_review', 'confirmed', 'dismissed', 'resolved', 'superseded')",
            name="ck_prov_judgment_previous_state",
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_prov_judgment_reason"),
        sa.CheckConstraint("length(trim(reviewer_ref)) > 0", name="ck_prov_judgment_reviewer"),
        sa.ForeignKeyConstraint(["finding_id"], ["provenance_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_decision_id"], ["review_decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "review_decision_id", name="uq_prov_judgment_review"),
    )
    op.create_index(op.f("ix_provenance_judgments_tenant_id"), "provenance_judgments", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_provenance_judgments_finding_id"), "provenance_judgments", ["finding_id"], unique=False)
    op.create_index(
        op.f("ix_provenance_judgments_review_decision_id"),
        "provenance_judgments",
        ["review_decision_id"],
        unique=False,
    )
    op.create_index("ix_prov_judgment_tenant_finding", "provenance_judgments", ["tenant_id", "finding_id"], unique=False)

    _enable_postgres_guards()


def downgrade() -> None:
    _disable_postgres_guards()
    op.drop_index("ix_prov_judgment_tenant_finding", table_name="provenance_judgments")
    op.drop_index(op.f("ix_provenance_judgments_review_decision_id"), table_name="provenance_judgments")
    op.drop_index(op.f("ix_provenance_judgments_finding_id"), table_name="provenance_judgments")
    op.drop_index(op.f("ix_provenance_judgments_tenant_id"), table_name="provenance_judgments")
    op.drop_table("provenance_judgments")
    op.drop_index(op.f("ix_provenance_finding_facts_fact_id"), table_name="provenance_finding_facts")
    op.drop_index(op.f("ix_provenance_finding_facts_finding_id"), table_name="provenance_finding_facts")
    op.drop_index(op.f("ix_provenance_finding_facts_tenant_id"), table_name="provenance_finding_facts")
    op.drop_table("provenance_finding_facts")
    op.drop_index("ix_prov_finding_tenant_case", table_name="provenance_findings")
    op.drop_index(op.f("ix_provenance_findings_supersedes_finding_id"), table_name="provenance_findings")
    op.drop_index(op.f("ix_provenance_findings_case_id"), table_name="provenance_findings")
    op.drop_index(op.f("ix_provenance_findings_tenant_id"), table_name="provenance_findings")
    op.drop_table("provenance_findings")
    op.drop_index(op.f("ix_provenance_derivation_inputs_fact_id"), table_name="provenance_derivation_inputs")
    op.drop_index(op.f("ix_provenance_derivation_inputs_derivation_id"), table_name="provenance_derivation_inputs")
    op.drop_index(op.f("ix_provenance_derivation_inputs_tenant_id"), table_name="provenance_derivation_inputs")
    op.drop_table("provenance_derivation_inputs")
    op.drop_index("ix_prov_fact_tenant_key", table_name="provenance_facts")
    op.drop_index(op.f("ix_provenance_facts_supersedes_fact_id"), table_name="provenance_facts")
    op.drop_index(op.f("ix_provenance_facts_origin_id"), table_name="provenance_facts")
    op.drop_index(op.f("ix_provenance_facts_tenant_id"), table_name="provenance_facts")
    op.drop_table("provenance_facts")
    op.drop_index("ix_prov_origin_tenant_type", table_name="provenance_origins")
    op.drop_index(op.f("ix_provenance_origins_derivation_id"), table_name="provenance_origins")
    op.drop_index(op.f("ix_provenance_origins_tenant_id"), table_name="provenance_origins")
    op.drop_table("provenance_origins")
    op.drop_index("ix_prov_derivation_tenant_created", table_name="provenance_derivations")
    op.drop_index(op.f("ix_provenance_derivations_tenant_id"), table_name="provenance_derivations")
    op.drop_table("provenance_derivations")
