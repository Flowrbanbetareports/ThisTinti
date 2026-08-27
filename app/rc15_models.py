from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import uid, utcnow


class RC15IntakeRecord(Base):
    __tablename__ = "rc15_intake_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subject_type", "subject_id", name="uq_rc15_intake_subject"),
        Index("ix_rc15_intake_tenant_updated", "tenant_id", "updated_at"),
        CheckConstraint("subject_type IN ('document', 'job')", name="ck_rc15_intake_subject_type"),
        CheckConstraint(
            "state IN ('acquired', 'review_required', 'not_acquired', 'blocked', 'out_of_scope')",
            name="ck_rc15_intake_state",
        ),
        CheckConstraint(
            "category IN ('ok', 'degraded', 'hostile', 'out_of_scope', 'parser_limit', 'operator_input', 'security_block')",
            name="ck_rc15_intake_category",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    automatic: Mapped[bool] = mapped_column(Boolean, default=True)
    classified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RC15CaseEconomicAssessment(Base):
    __tablename__ = "rc15_case_economic_assessments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "case_id", name="uq_rc15_case_economic_case"),
        CheckConstraint("potential_exposure IS NULL OR potential_exposure >= 0", name="ck_rc15_potential_nonnegative"),
        CheckConstraint("confirmed_loss IS NULL OR confirmed_loss >= 0", name="ck_rc15_loss_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("discrepancy_cases.id", ondelete="CASCADE"), index=True)
    potential_exposure: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    confirmed_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    note: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RC15CompanyProfileVersion(Base):
    __tablename__ = "rc15_company_profile_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_rc15_company_profile_version"),
        UniqueConstraint("tenant_id", "config_hash", name="uq_rc15_company_profile_hash"),
        Index("ix_rc15_company_profile_active", "tenant_id", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RC15Practice(Base):
    __tablename__ = "rc15_practices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "chain_id", name="uq_rc15_practice_chain"),
        Index("ix_rc15_practice_tenant_status", "tenant_id", "status"),
        CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_rc15_practice_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    chain_id: Mapped[str | None] = mapped_column(ForeignKey("operation_chains.id", ondelete="SET NULL"), nullable=True)
    profile_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rc15_company_profile_versions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    retention_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    tombstone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RC15PilotWorkspace(Base):
    __tablename__ = "rc15_pilot_workspaces"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_rc15_pilot_version"),
        Index("ix_rc15_pilot_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('draft', 'frozen', 'running', 'completed', 'archived')",
            name="ck_rc15_pilot_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    authorization_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    reviewer_primary: Mapped[str] = mapped_column(String(120), nullable=False)
    reviewer_secondary: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    retention_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    profile_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rc15_company_profile_versions.id", ondelete="SET NULL"), nullable=True
    )
    ground_truth_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    freeze_manifest_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RC15PilotCase(Base):
    __tablename__ = "rc15_pilot_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "pilot_id", "practice_id", name="uq_rc15_pilot_practice"),
        Index("ix_rc15_pilot_case_pilot", "tenant_id", "pilot_id"),
        CheckConstraint("manual_seconds IS NULL OR manual_seconds > 0", name="ck_rc15_manual_seconds"),
        CheckConstraint("assisted_seconds IS NULL OR assisted_seconds > 0", name="ck_rc15_assisted_seconds"),
        CheckConstraint("user_score IS NULL OR (user_score >= 1 AND user_score <= 5)", name="ck_rc15_user_score"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    pilot_id: Mapped[str] = mapped_column(ForeignKey("rc15_pilot_workspaces.id", ondelete="CASCADE"), index=True)
    practice_id: Mapped[str] = mapped_column(ForeignKey("rc15_practices.id", ondelete="RESTRICT"), index=True)
    reviewer_primary_json: Mapped[str] = mapped_column(Text, default="{}")
    reviewer_secondary_json: Mapped[str] = mapped_column(Text, default="{}")
    adjudicated_json: Mapped[str] = mapped_column(Text, default="{}")
    manual_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    assisted_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
