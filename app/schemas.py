from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

DocumentType = Literal["proposal", "order", "confirmation", "delivery", "invoice", "payment", "return", "credit_note"]


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    legal_notice_version: str | None = None
    accepted_terms: bool = False
    accepted_specific_clauses: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict[str, Any]


class AuthUserResponse(BaseModel):
    id: str
    tenant_id: str
    email: EmailStr
    role: str
    organization: str


class AuthResponse(BaseModel):
    user: AuthUserResponse
    token: str | None = None


class OkResponse(BaseModel):
    ok: bool


class ReadinessResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]
    details: dict[str, Any] = Field(default_factory=dict)


class ProcessingJobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    priority: int
    attempts: int
    max_attempts: int
    progress: int
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class ProcessingJobEnvelopeResponse(BaseModel):
    job: ProcessingJobResponse
    created: bool


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str


class DocumentLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    line_no: int
    sku: str | None
    description: str | None
    color: str | None
    size: str | None
    lot: str | None
    unit_of_measure: str | None = None
    quantity: float
    unit_price: float
    price_base_quantity: float = 1.0
    discount_rate: float
    tax_rate: float
    line_total: float
    canonical_key: str | None
    confidence: float


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_type: str
    number: str | None
    document_date: date | None
    currency: str
    source_filename: str
    parse_status: str
    parse_message: str | None
    confidence: float
    created_at: datetime
    lines: list[DocumentLineResponse] = []


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str | None
    document_line_id: str | None
    field_name: str
    observed_value: str | None
    expected_value: str | None
    note: str | None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    chain_id: str
    case_type: str
    severity: str
    amount_estimate: float
    confidence: float
    status: str
    title: str
    explanation: str
    recommended_action: str
    created_at: datetime
    evidence: list[EvidenceResponse] = []


class IntelligenceSimulationRequest(BaseModel):
    action: Literal["approve_invoice", "approve_payment", "accept_delivery"] = "approve_invoice"


class ProofGraphNodeResponse(BaseModel):
    id: str
    kind: str
    role: str | None = None
    label: str
    status: str
    confidence: float
    document_id: str | None = None
    amount: float = 0.0
    date: str | None = None
    evidence_strength: str


class ProofGraphEdgeResponse(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    confidence: float
    reason: str


class ProofGraphResponse(BaseModel):
    chain_id: str
    reference_key: str | None = None
    nodes: list[ProofGraphNodeResponse]
    edges: list[ProofGraphEdgeResponse]
    summary: dict[str, Any]


class ExpectationResponse(BaseModel):
    role: str
    label: str
    status: str
    required: bool
    due_date: date | None = None
    confidence: float
    rationale: str
    source_document_ids: list[str]
    risk_if_missing: str
    timing_source: str
    sample_count: int


class RiskAssessmentResponse(BaseModel):
    chain_id: str
    action: str
    score: float
    level: str
    decision: str
    safe_to_automate: bool
    amount_at_risk: float
    reasons: list[str]
    payment_reconciliation: dict[str, Any]
    process_conformance: dict[str, Any]
    proof_contract: list[dict[str, Any]]
    calibration: dict[str, Any]
    uncertainty: dict[str, Any]


class RedTeamResponse(BaseModel):
    chain_id: str
    status: str
    coverage: float
    detected: int
    applicable: int
    total: int
    scenarios: list[dict[str, Any]]
    note: str


class AnonymousPatternPackResponse(BaseModel):
    format: str
    format_version: int
    engine_version: str
    privacy: dict[str, Any]
    process_variants: list[dict[str, Any]]
    rare_variant_count_bucket: str
    rule_capabilities: list[dict[str, Any]]
    validation: dict[str, Any]
    sample_size: dict[str, str]
    pack_hash: str


class ChainIntelligenceResponse(BaseModel):
    chain_id: str
    proof_graph: ProofGraphResponse
    expectations: list[ExpectationResponse]
    risk: RiskAssessmentResponse
    process_conformance: dict[str, Any]
    triangulation: dict[str, Any]
    learning: dict[str, Any]


class ReviewRequest(BaseModel):
    decision: Literal["confirmed", "dismissed", "needs_review", "resolved"]
    note: str | None = Field(default=None, max_length=2000)


class DashboardResponse(BaseModel):
    documents: int
    cases_open: int
    chains: int
    amount_potential: float
    parsing_failures: int
    confidence_average: float


class ReprocessRequest(BaseModel):
    document_type: DocumentType | None = None
    supplier_name: str | None = Field(default=None, max_length=240)
    number: str | None = Field(default=None, max_length=120)
    document_date: date | None = None


class ChainAttachRequest(BaseModel):
    document_id: str
    role: DocumentType


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    role: Literal["admin", "reviewer", "viewer"] = "viewer"


class UserStatusRequest(BaseModel):
    active: bool


class UserRoleRequest(BaseModel):
    role: Literal["admin", "reviewer", "viewer"]


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=256)


class ApiCredentialCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    role: Literal["reviewer", "viewer"] = "viewer"
    scopes: list[Literal["read", "ingest", "review"]] = Field(default_factory=lambda: ["read"])
    expires_at: datetime | None = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=10, max_length=256)


class ValidationExpectedFinding(BaseModel):
    case_type: str = Field(min_length=2, max_length=80)
    amount: float | None = None
    amount_tolerance: float = Field(default=0.05, ge=0, le=1)
    absolute_tolerance: float = Field(default=0.05, ge=0, le=1000000)


class ValidationDocumentInput(BaseModel):
    filename: str = Field(min_length=1, max_length=180)
    mime_type: str = Field(default="application/json", max_length=150)
    content: dict[str, Any]


class ValidationScenarioInput(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    documents: list[ValidationDocumentInput] = Field(min_length=1, max_length=30)
    expected: list[ValidationExpectedFinding] = Field(default_factory=list, max_length=100)
    ignore_unexpected_types: list[str] = Field(default_factory=list, max_length=100)


class ValidationGate(BaseModel):
    min_precision: float = Field(default=0.95, ge=0, le=1)
    min_recall: float = Field(default=0.95, ge=0, le=1)
    min_f1: float = Field(default=0.95, ge=0, le=1)
    max_amount_mae: float = Field(default=1.0, ge=0)
    require_all_scenarios_pass: bool = True


class ValidationEvidenceMetadata(BaseModel):
    authorization_reference: str = Field(min_length=3, max_length=240)
    authorized_use_confirmed: bool = False
    anonymization_confirmed: bool = False
    anonymization_method: str | None = Field(default=None, min_length=3, max_length=1000)
    reviewer_refs: list[str] = Field(min_length=2, max_length=20)
    ground_truth_method: str = Field(min_length=10, max_length=2000)
    scope: str = Field(min_length=10, max_length=2000)
    prepared_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_reviewers(self) -> "ValidationEvidenceMetadata":
        normalized = [item.strip().casefold() for item in self.reviewer_refs if item.strip()]
        if len(normalized) < 2 or len(set(normalized)) < 2:
            raise ValueError("At least two distinct reviewer references are required")
        return self


class ValidationDatasetPayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    version: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=3000)
    evidence_level: Literal["synthetic", "anonymized_pilot", "production"] = "synthetic"
    automation_eligible: bool = False
    evidence: ValidationEvidenceMetadata | None = None
    gate: ValidationGate = Field(default_factory=ValidationGate)
    scenarios: list[ValidationScenarioInput] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_automation_evidence(self) -> "ValidationDatasetPayload":
        if self.automation_eligible:
            raise ValueError("Use the audited automation approval endpoint after a successful real-data gate")
        if self.evidence_level == "synthetic":
            return self
        if self.evidence is None:
            raise ValueError("Real-evidence datasets require authorization, reviewers and ground-truth metadata")
        if not self.evidence.authorized_use_confirmed:
            raise ValueError("Authorized use must be explicitly confirmed for real-evidence datasets")
        if len(self.scenarios) < 30:
            raise ValueError("Real-evidence datasets require at least 30 independent scenarios")
        if self.evidence_level == "anonymized_pilot":
            if not self.evidence.anonymization_confirmed:
                raise ValueError("Anonymization must be explicitly confirmed for an anonymized pilot")
            if not self.evidence.anonymization_method:
                raise ValueError("An anonymization method is required for an anonymized pilot")
        return self


class ValidationDatasetStatusRequest(BaseModel):
    status: Literal["active", "archived"]


class ValidationAutomationApprovalRequest(BaseModel):
    enabled: bool
    note: str = Field(min_length=10, max_length=2000)


class ValidationAutomationApprovalResponse(BaseModel):
    ok: bool
    dataset_id: str
    automation_eligible: bool
    evidence_level: str
    validation_run_id: str | None = None


class ItemAliasConfirmRequest(BaseModel):
    canonical_line_id: str = Field(min_length=1, max_length=36)
    alias_line_id: str = Field(min_length=1, max_length=36)


class RuleDecisionRequest(BaseModel):
    decision: Literal["confirmed", "rejected", "inactive"]
    note: str | None = Field(default=None, max_length=2000)


class DiscoveryRunRequest(BaseModel):
    force_relearn: bool = False
    minimum_documents: int = Field(default=3, ge=1, le=1000)
    auto_activate_threshold: float = Field(default=0.92, ge=0.5, le=1.0)
    confirmation_threshold: float = Field(default=0.68, ge=0.2, le=0.99)


class ActivityProfileDecisionRequest(BaseModel):
    decision: Literal["confirmed", "corrected", "relearn"]
    activity_type: str | None = Field(default=None, min_length=2, max_length=120)
    activity_label: str | None = Field(default=None, min_length=2, max_length=180)
