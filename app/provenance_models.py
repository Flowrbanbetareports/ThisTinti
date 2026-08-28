from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    update,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import Document, uid, utcnow


ORIGIN_TYPES = (
    "DOCUMENT_EVIDENCE",
    "HUMAN_ASSERTION",
    "MASTER_DATA_IMPORT",
    "SYSTEM_OBSERVATION",
    "DETERMINISTIC_DERIVATION",
    "LEGACY_ORIGIN_UNKNOWN",
)
SOURCE_AVAILABILITY_STATES = (
    "available",
    "deleted_by_retention",
    "not_stored",
    "access_denied",
    "external_unavailable",
    "legacy_unknown",
)
LOCATOR_STATUSES = ("present", "missing", "not_applicable")
LOCATOR_TYPES = (
    "PDF_PAGE_BOX",
    "IMAGE_BOX",
    "TEXT_RANGE",
    "CSV_CELL",
    "XLSX_CELL",
    "JSON_POINTER",
    "XPATH",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class ProvenanceDerivation(Base):
    __tablename__ = "provenance_derivations"
    __table_args__ = (Index("ix_prov_derivation_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    transformation_id: Mapped[str] = mapped_column(String(240), nullable=False)
    engine_id: Mapped[str] = mapped_column(String(160), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(120), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProvenanceOrigin(Base):
    __tablename__ = "provenance_origins"
    __table_args__ = (
        Index("ix_prov_origin_tenant_type", "tenant_id", "origin_type"),
        CheckConstraint(f"origin_type IN ({_quoted(ORIGIN_TYPES)})", name="ck_prov_origin_type"),
        CheckConstraint(
            f"source_availability IS NULL OR source_availability IN ({_quoted(SOURCE_AVAILABILITY_STATES)})",
            name="ck_prov_source_availability",
        ),
        CheckConstraint(
            f"locator_status IS NULL OR locator_status IN ({_quoted(LOCATOR_STATUSES)})",
            name="ck_prov_locator_status",
        ),
        CheckConstraint(
            f"locator_type IS NULL OR locator_type IN ({_quoted(LOCATOR_TYPES)})",
            name="ck_prov_locator_type",
        ),
        CheckConstraint(
            "(locator_status IS NULL) OR "
            "(locator_status = 'present' AND locator_type IS NOT NULL AND locator_json IS NOT NULL) OR "
            "(locator_status IN ('missing', 'not_applicable') AND locator_type IS NULL)",
            name="ck_prov_locator_shape",
        ),
        CheckConstraint(
            "origin_type != 'DOCUMENT_EVIDENCE' OR "
            "(source_ref IS NOT NULL AND source_availability IS NOT NULL AND locator_status IS NOT NULL)",
            name="ck_prov_document_origin",
        ),
        CheckConstraint(
            "origin_type != 'HUMAN_ASSERTION' OR "
            "(actor_ref IS NOT NULL AND asserted_at IS NOT NULL AND reason IS NOT NULL)",
            name="ck_prov_human_origin",
        ),
        CheckConstraint(
            "origin_type != 'MASTER_DATA_IMPORT' OR (source_ref IS NOT NULL AND imported_at IS NOT NULL)",
            name="ck_prov_master_origin",
        ),
        CheckConstraint(
            "origin_type != 'SYSTEM_OBSERVATION' OR "
            "(engine_id IS NOT NULL AND engine_version IS NOT NULL AND observed_at IS NOT NULL)",
            name="ck_prov_system_origin",
        ),
        CheckConstraint(
            "origin_type != 'DETERMINISTIC_DERIVATION' OR derivation_id IS NOT NULL",
            name="ck_prov_derivation_origin",
        ),
        CheckConstraint(
            "origin_type != 'LEGACY_ORIGIN_UNKNOWN' OR legacy_marker IS NOT NULL",
            name="ck_prov_legacy_origin",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    origin_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    source_availability: Mapped[str | None] = mapped_column(String(40), nullable=True)
    locator_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    locator_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    locator_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    asserted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engine_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    configuration_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    derivation_id: Mapped[str | None] = mapped_column(
        ForeignKey("provenance_derivations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    legacy_marker: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProvenanceFact(Base):
    __tablename__ = "provenance_facts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fact_key", "version", name="uq_prov_fact_version"),
        Index("ix_prov_fact_tenant_key", "tenant_id", "fact_key"),
        CheckConstraint("version >= 1", name="ck_prov_fact_version_positive"),
        CheckConstraint(
            "(version = 1 AND supersedes_fact_id IS NULL) OR (version > 1 AND supersedes_fact_id IS NOT NULL)",
            name="ck_prov_fact_supersession",
        ),
        CheckConstraint("supersedes_fact_id IS NULL OR supersedes_fact_id != id", name="ck_prov_fact_not_self"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    fact_key: Mapped[str] = mapped_column(String(300), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    fact_type: Mapped[str] = mapped_column(String(160), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    origin_id: Mapped[str] = mapped_column(ForeignKey("provenance_origins.id", ondelete="CASCADE"), index=True)
    supersedes_fact_id: Mapped[str | None] = mapped_column(ForeignKey("provenance_facts.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProvenanceDerivationInput(Base):
    __tablename__ = "provenance_derivation_inputs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "derivation_id", "fact_id", name="uq_prov_derivation_fact"),
        UniqueConstraint("tenant_id", "derivation_id", "position", name="uq_prov_derivation_position"),
        CheckConstraint("position >= 1", name="ck_prov_derivation_position_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    derivation_id: Mapped[str] = mapped_column(ForeignKey("provenance_derivations.id", ondelete="CASCADE"), index=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("provenance_facts.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class ProvenanceFinding(Base):
    __tablename__ = "provenance_findings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "case_id", "version", name="uq_prov_finding_version"),
        Index("ix_prov_finding_tenant_case", "tenant_id", "case_id"),
        CheckConstraint("version >= 1", name="ck_prov_finding_version_positive"),
        CheckConstraint(
            "(version = 1 AND supersedes_finding_id IS NULL) OR (version > 1 AND supersedes_finding_id IS NOT NULL)",
            name="ck_prov_finding_supersession",
        ),
        CheckConstraint(
            "supersedes_finding_id IS NULL OR supersedes_finding_id != id",
            name="ck_prov_finding_not_self",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("discrepancy_cases.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_id: Mapped[str] = mapped_column(String(240), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_finding_id: Mapped[str | None] = mapped_column(
        ForeignKey("provenance_findings.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProvenanceFindingFact(Base):
    __tablename__ = "provenance_finding_facts"
    __table_args__ = (UniqueConstraint("tenant_id", "finding_id", "fact_id", name="uq_prov_finding_fact"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("provenance_findings.id", ondelete="CASCADE"), index=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("provenance_facts.id", ondelete="RESTRICT"), index=True)
    role: Mapped[str] = mapped_column(String(80), default="supporting")


class ProvenanceJudgment(Base):
    __tablename__ = "provenance_judgments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "review_decision_id", name="uq_prov_judgment_review"),
        Index("ix_prov_judgment_tenant_finding", "tenant_id", "finding_id"),
        CheckConstraint(
            "decision IN ('confirmed', 'dismissed', 'needs_review', 'resolved')",
            name="ck_prov_judgment_decision",
        ),
        CheckConstraint(
            "previous_state IN ('open', 'needs_review', 'confirmed', 'dismissed', 'resolved', 'superseded')",
            name="ck_prov_judgment_previous_state",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="ck_prov_judgment_reason"),
        CheckConstraint("length(trim(reviewer_ref)) > 0", name="ck_prov_judgment_reviewer"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("provenance_findings.id", ondelete="CASCADE"), index=True)
    review_decision_id: Mapped[str] = mapped_column(ForeignKey("review_decisions.id", ondelete="CASCADE"), index=True)
    reviewer_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    reviewer_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    previous_state: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


@event.listens_for(Document, "before_delete")
def _mark_document_evidence_unavailable(_mapper, connection, target: Document) -> None:
    """Keep source availability truthful when the controlled local lifecycle deletes a document."""
    connection.execute(
        update(ProvenanceOrigin.__table__)
        .where(
            ProvenanceOrigin.document_id == target.id,
            ProvenanceOrigin.origin_type == "DOCUMENT_EVIDENCE",
            ProvenanceOrigin.source_availability == "available",
        )
        .values(document_id=None, source_availability="deleted_by_retention")
    )
