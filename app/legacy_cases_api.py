from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import add_audit
from .db import get_db
from .models import DiscrepancyCase, ReviewDecision
from .schemas import ReviewRequest
from .security import AuthContext, require_reviewer
from .services.judgment_provenance import (
    lock_p1_support_for_update,
    record_judgment_provenance,
    resolve_reviewer_identity,
)


router = APIRouter()

_P1_PROVENANCE_CASE_TYPES = frozenset(
    {
        "duplicate_document_number",
        "currency_mismatch",
        "delivered_over_order",
        "invoiced_over_received",
        "payment_over_invoice",
        "payment_without_invoice",
    }
)


def _case_query(*, case_id: str, tenant_id: str):
    return select(DiscrepancyCase).where(
        DiscrepancyCase.id == case_id,
        DiscrepancyCase.tenant_id == tenant_id,
    )


def _locked_case_query(*, case_id: str, tenant_id: str):
    # The review path first reads the case without a lock so it knows which
    # support chain must be locked. A concurrent transaction can change the
    # case between that read and this row lock. Force the locked SELECT to
    # refresh an already-present identity-map object so the drift cannot be
    # hidden by stale ORM state.
    return (
        _case_query(case_id=case_id, tenant_id=tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _case_support_identity_is_stable(
    case: DiscrepancyCase,
    *,
    observed_case_type: str,
    observed_chain_id: str,
) -> bool:
    """Reject a review when the case identity changed before its row lock."""
    return case.case_type == observed_case_type and case.chain_id == observed_chain_id


@router.post(
    "/api/cases/{case_id}/decision",
    summary="Review Case",
    operation_id="review_case_api_cases__case_id__decision_post",
)
def review_case_with_provenance(
    case_id: str,
    payload: ReviewRequest,
    ctx: AuthContext = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> dict:
    case = db.scalar(_case_query(case_id=case_id, tenant_id=ctx.tenant_id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    observed_case_type = case.case_type
    observed_chain_id = case.chain_id
    if observed_case_type in _P1_PROVENANCE_CASE_TYPES:
        if not lock_p1_support_for_update(
            db,
            tenant_id=ctx.tenant_id,
            chain_id=observed_chain_id,
        ):
            db.rollback()
            raise HTTPException(status_code=409, detail="Case support chain is unavailable")

    case = db.scalar(_locked_case_query(case_id=case_id, tenant_id=ctx.tenant_id))
    if case is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Case not found")
    if not _case_support_identity_is_stable(
        case,
        observed_case_type=observed_case_type,
        observed_chain_id=observed_chain_id,
    ):
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Case support identity changed during review; retry against current evidence",
        )

    previous_state = case.status
    reviewer_ref, reviewer_user_id = resolve_reviewer_identity(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
    )
    decision = ReviewDecision(
        tenant_id=ctx.tenant_id,
        case_id=case.id,
        user_id=reviewer_user_id,
        decision=payload.decision,
        note=payload.note,
    )
    db.add(decision)
    db.flush()
    judgment = record_judgment_provenance(
        db,
        tenant_id=ctx.tenant_id,
        case_id=case.id,
        review_decision=decision,
        reviewer_ref=reviewer_ref,
        reviewer_user_id=reviewer_user_id,
        previous_state=previous_state,
    )
    if case.case_type in _P1_PROVENANCE_CASE_TYPES and judgment is None:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Case decision requires exact-current provenance support",
        )

    case.status = payload.decision
    add_audit(
        db,
        ctx.tenant_id,
        "case.reviewed",
        ctx.user_id,
        "discrepancy_case",
        case.id,
        {"decision": payload.decision, "note": payload.note},
    )
    db.commit()
    return {"ok": True, "status": case.status}
