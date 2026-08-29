from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import add_audit
from .db import get_db
from .models import DiscrepancyCase, ReviewDecision
from .schemas import ReviewRequest
from .security import AuthContext, require_reviewer
from .services.judgment_provenance import record_judgment_provenance, resolve_reviewer_identity


router = APIRouter()


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
    case = db.scalar(
        select(DiscrepancyCase).where(
            DiscrepancyCase.id == case_id,
            DiscrepancyCase.tenant_id == ctx.tenant_id,
        )
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    previous_state = case.status
    reviewer_ref, reviewer_user_id = resolve_reviewer_identity(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
    )
    case.status = payload.decision
    decision = ReviewDecision(
        tenant_id=ctx.tenant_id,
        case_id=case.id,
        user_id=reviewer_user_id,
        decision=payload.decision,
        note=payload.note,
    )
    db.add(decision)
    db.flush()
    record_judgment_provenance(
        db,
        tenant_id=ctx.tenant_id,
        case_id=case.id,
        review_decision=decision,
        reviewer_ref=reviewer_ref,
        reviewer_user_id=reviewer_user_id,
        previous_state=previous_state,
    )
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
