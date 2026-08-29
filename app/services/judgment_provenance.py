from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ApiCredential, ReviewDecision, User
from ..provenance_models import ProvenanceFinding, ProvenanceJudgment
from .delivered_over_order_provenance import delivered_over_order_finding_matches_current_support
from .finding_provenance import (
    currency_mismatch_finding_matches_current_support,
    duplicate_number_finding_matches_current_support,
)
from .invoiced_over_received_provenance import invoiced_over_received_finding_matches_current_support


def resolve_reviewer_identity(
    db: Session,
    *,
    tenant_id: str,
    actor_id: str | None,
) -> tuple[str | None, str | None]:
    """Return a stable provenance reviewer reference and optional User FK."""
    if not actor_id:
        return None, None

    user_id = db.scalar(
        select(User.id).where(
            User.id == actor_id,
            User.tenant_id == tenant_id,
        )
    )
    if user_id is not None:
        return f"user:{user_id}", user_id

    credential_id = db.scalar(
        select(ApiCredential.id).where(
            ApiCredential.id == actor_id,
            ApiCredential.tenant_id == tenant_id,
        )
    )
    if credential_id is not None:
        return f"api_credential:{credential_id}", None

    return None, None


def record_judgment_provenance(
    db: Session,
    *,
    tenant_id: str,
    case_id: str,
    review_decision: ReviewDecision,
    reviewer_ref: str | None,
    reviewer_user_id: str | None,
    previous_state: str,
) -> ProvenanceJudgment | None:
    """Link a human review decision to the latest currently provable finding version."""
    if not reviewer_ref or not review_decision.note or not review_decision.note.strip():
        return None

    existing = db.scalar(
        select(ProvenanceJudgment).where(
            ProvenanceJudgment.tenant_id == tenant_id,
            ProvenanceJudgment.review_decision_id == review_decision.id,
        )
    )
    if existing is not None:
        return existing

    finding = db.scalar(
        select(ProvenanceFinding)
        .where(
            ProvenanceFinding.tenant_id == tenant_id,
            ProvenanceFinding.case_id == case_id,
        )
        .order_by(ProvenanceFinding.version.desc())
        .limit(1)
    )
    if finding is None:
        return None
    if finding.rule_id == "builtin:duplicate_document_number" and not duplicate_number_finding_matches_current_support(
        db, finding=finding
    ):
        return None
    if finding.rule_id == "builtin:currency_mismatch" and not currency_mismatch_finding_matches_current_support(
        db, finding=finding
    ):
        return None
    if finding.rule_id == "builtin:delivered_over_order" and not delivered_over_order_finding_matches_current_support(
        db, finding=finding
    ):
        return None
    if (
        finding.rule_id == "builtin:invoiced_over_received"
        and not invoiced_over_received_finding_matches_current_support(db, finding=finding)
    ):
        return None

    judgment = ProvenanceJudgment(
        tenant_id=tenant_id,
        finding_id=finding.id,
        review_decision_id=review_decision.id,
        reviewer_ref=reviewer_ref,
        reviewer_user_id=reviewer_user_id,
        decision=review_decision.decision,
        reason=review_decision.note.strip(),
        previous_state=previous_state,
    )
    db.add(judgment)
    db.flush()
    return judgment
