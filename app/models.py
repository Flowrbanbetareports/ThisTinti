from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint("status IN ('active', 'suspended', 'deleted')", name="ck_tenant_status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active")
    security_version: Mapped[int] = mapped_column(Integer, default=0)
    audit_sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    users: Mapped[list[User]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
        CheckConstraint("role IN ('admin', 'reviewer', 'viewer')", name="ck_user_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="admin")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_session_user_active", "user_id", "active"),
        Index("ix_auth_session_tenant_active", "tenant_id", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ApiCredential(Base):
    __tablename__ = "api_credentials"
    __table_args__ = (
        Index("ix_api_credential_tenant_active", "tenant_id", "active"),
        CheckConstraint("role IN ('reviewer', 'viewer')", name="ck_api_credential_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="viewer")
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_job_tenant_idempotency"),
        Index("ix_job_claim", "status", "available_at", "created_at"),
        Index("ix_job_tenant_created", "tenant_id", "created_at"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_processing_job_status",
        ),
        CheckConstraint(
            "job_type IN ('ingest_document', 'ingest_batch', 'reprocess_document', 'reanalyze_tenant', 'red_team_tenant')",
            name="ck_processing_job_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_api_credential: Mapped[str | None] = mapped_column(
        ForeignKey("api_credentials.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    version: Mapped[str] = mapped_column(String(40), default="unknown")


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("tenant_id", "normalized_name", name="uq_supplier_tenant_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(240), nullable=False)
    vat_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupplierAlias(Base):
    __tablename__ = "supplier_aliases"
    __table_args__ = (UniqueConstraint("tenant_id", "normalized_alias", name="uq_supplier_alias"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(240), nullable=False)


class ItemAlias(Base):
    __tablename__ = "item_aliases"
    __table_args__ = (UniqueConstraint("tenant_id", "supplier_id", "normalized_alias", name="uq_item_alias"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=True)
    canonical_key: Mapped[str] = mapped_column(String(500), nullable=False)
    alias: Mapped[str] = mapped_column(String(280), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(280), nullable=False)
    confirmed_count: Mapped[int] = mapped_column(Integer, default=1)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_document_tenant_supplier_type", "tenant_id", "supplier_id", "document_type"),
        UniqueConstraint("tenant_id", "file_hash", name="uq_document_hash_per_tenant"),
        CheckConstraint(
            "document_type IN ('proposal', 'order', 'confirmation', 'delivery', 'invoice', 'payment', 'return', 'credit_note')",
            name="ck_document_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    document_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(30), default="pending")
    parse_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    references_json: Mapped[str] = mapped_column(Text, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lines: Mapped[list[DocumentLine]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentLine(Base):
    __tablename__ = "document_lines"
    __table_args__ = (Index("ix_line_tenant_document", "tenant_id", "document_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column(Integer, default=0)
    sku: Mapped[str | None] = mapped_column(String(280), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(24, 10), default=0)
    price_base_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=1)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=0)
    canonical_key: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")

    document: Mapped[Document] = relationship(back_populates="lines")


class OperationChain(Base):
    __tablename__ = "operation_chains"
    __table_args__ = (Index("ix_chain_tenant_supplier", "tenant_id", "supplier_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    proposal_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    order_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    confirmation_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    delivery_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    invoice_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    payment_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    return_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    credit_note_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    reference_key: Mapped[str | None] = mapped_column(String(280), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ChainDocument(Base):
    __tablename__ = "chain_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_id", name="uq_chain_document"),
        Index("ix_chain_document_role", "tenant_id", "chain_id", "role"),
        CheckConstraint(
            "role IN ('proposal', 'order', 'confirmation', 'delivery', 'invoice', 'payment', 'return', 'credit_note')",
            name="ck_chain_document_role",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    chain_id: Mapped[str] = mapped_column(ForeignKey("operation_chains.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1)
    match_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    match_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiscrepancyCase(Base):
    __tablename__ = "discrepancy_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_case_fingerprint"),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_case_severity"),
        CheckConstraint(
            "status IN ('open', 'needs_review', 'confirmed', 'dismissed', 'resolved', 'superseded')",
            name="ck_case_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    chain_id: Mapped[str] = mapped_column(ForeignKey("operation_chains.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    case_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    amount_estimate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="open")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, default="Review manually")
    machine_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    evidence: Mapped[list[EvidenceLink]] = relationship(back_populates="case", cascade="all, delete-orphan")


class EvidenceLink(Base):
    __tablename__ = "evidence_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("discrepancy_cases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    document_line_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_lines.id", ondelete="SET NULL"), nullable=True
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    observed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[DiscrepancyCase] = relationship(back_populates="evidence")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('confirmed', 'dismissed', 'needs_review', 'resolved')",
            name="ck_review_decision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("discrepancy_cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ValidationDataset(Base):
    __tablename__ = "validation_datasets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_validation_dataset_version"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_validation_dataset_status"),
        CheckConstraint(
            "evidence_level IN ('synthetic', 'anonymized_pilot', 'production')",
            name="ck_validation_dataset_evidence_level",
        ),
        CheckConstraint(
            "NOT automation_eligible OR evidence_level IN ('anonymized_pilot', 'production')",
            name="ck_validation_dataset_automation_evidence",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    evidence_level: Mapped[str] = mapped_column(String(30), default="synthetic")
    automation_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    runs: Mapped[list[ValidationRun]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    __table_args__ = (
        Index("ix_validation_run_tenant_created", "tenant_id", "created_at"),
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_validation_run_status"),
        CheckConstraint(
            "NOT automation_approved OR "
            "(automation_approved_by IS NOT NULL AND automation_approved_at IS NOT NULL "
            "AND automation_approval_note IS NOT NULL)",
            name="ck_validation_run_approval_evidence",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("validation_datasets.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    scenario_count: Mapped[int] = mapped_column(Integer, default=0)
    true_positives: Mapped[int] = mapped_column(Integer, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, default=0)
    false_negatives: Mapped[int] = mapped_column(Integer, default=0)
    precision: Mapped[float] = mapped_column(Float, default=0.0)
    recall: Mapped[float] = mapped_column(Float, default=0.0)
    f1_score: Mapped[float] = mapped_column(Float, default=0.0)
    amount_mae: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_approved_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    automation_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    automation_approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dataset: Mapped[ValidationDataset] = relationship(back_populates="runs")


class ActivityProfile(Base):
    __tablename__ = "activity_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_activity_profile_tenant"),
        CheckConstraint(
            "status IN ('learning', 'ready', 'needs_confirmation')",
            name="ck_activity_profile_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    activity_type: Mapped[str] = mapped_column(String(120), default="generic_commerce")
    activity_label: Mapped[str] = mapped_column(String(180), default="Attività commerciale generica")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="learning")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    field_profile_json: Mapped[str] = mapped_column(Text, default="{}")
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"
    __table_args__ = (
        Index("ix_discovery_run_tenant_created", "tenant_id", "created_at"),
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_discovery_run_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    activity_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    activity_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    proposed_rules: Mapped[int] = mapped_column(Integer, default=0)
    auto_activated_rules: Mapped[int] = mapped_column(Integer, default=0)
    uncertain_rules: Mapped[int] = mapped_column(Integer, default=0)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RuleProposal(Base):
    __tablename__ = "rule_proposals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_code", name="uq_rule_proposal_tenant_code"),
        CheckConstraint(
            "status IN ('auto_active', 'needs_confirmation', 'confirmed', 'rejected', 'inactive')",
            name="ck_rule_proposal_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="needs_confirmation")
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    source: Mapped[str] = mapped_column(String(30), default="discovered")
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint("tenant_id", "sequence_no", name="uq_audit_tenant_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
