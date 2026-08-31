from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ApiCredential,
    ChainDocument,
    DiscrepancyCase,
    Document,
    DocumentLine,
    OperationChain,
    ReviewDecision,
    User,
)
from ..provenance_models import ProvenanceFinding, ProvenanceJudgment
from .delivered_over_order_provenance import delivered_over_order_finding_matches_current_support
from .finding_provenance import (
    currency_mismatch_finding_matches_current_support,
    duplicate_number_finding_matches_current_support,
)
from .invoiced_over_received_provenance import invoiced_over_received_finding_matches_current_support
from .payment_over_invoice_provenance import payment_over_invoice_finding_matches_current_support
from .payment_without_invoice_provenance import payment_without_invoice_finding_matches_current_support


FindingSupportMatcher = Callable[[Session], bool]

_P1_RULE_MATCHERS = {
    "duplicate_document_number": (
        "builtin:duplicate_document_number",
        duplicate_number_finding_matches_current_support,
    ),
    "currency_mismatch": (
        "builtin:currency_mismatch",
        currency_mismatch_finding_matches_current_support,
    ),
    "delivered_over_order": (
        "builtin:delivered_over_order",
        delivered_over_order_finding_matches_current_support,
    ),
    "invoiced_over_received": (
        "builtin:invoiced_over_received",
        invoiced_over_received_finding_matches_current_support,
    ),
    "payment_over_invoice": (
        "builtin:payment_over_invoice",
        payment_over_invoice_finding_matches_current_support,
    ),
    "payment_without_invoice": (
        "builtin:payment_without_invoice",
        payment_without_invoice_finding_matches_current_support,
    ),
}


def lock_p1_support_for_update(
    db: Session,
    *,
    tenant_id: str,
    chain_id: str,
) -> bool:
    """Lock a P1 chain and its current document support before judgment validation.

    The lock order deliberately starts from the chain, then membership rows, documents,
    and document lines. Support-changing transactions that already hold a document/line
    lock must finish before this function returns; transactions that have only staged a
    mutation cannot commit that mutation until this judgment transaction releases the
    locked support rows. This closes the evidence-mutation vs judgment-commit TOCTOU
    without relying on an inherited/stale support check.
    """
    with db.no_autoflush:
        chain = db.scalar(
            select(OperationChain)
            .where(
                OperationChain.id == chain_id,
                OperationChain.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if chain is None:
            return False

        links = list(
            db.scalars(
                select(ChainDocument)
                .where(
                    ChainDocument.tenant_id == tenant_id,
                    ChainDocument.chain_id == chain_id,
                )
                .order_by(ChainDocument.id)
                .with_for_update()
            )
        )
        document_ids = {link.document_id for link in links}
        for role in (
            "proposal",
            "order",
            "confirmation",
            "delivery",
            "invoice",
            "payment",
            "return",
            "credit_note",
        ):
            document_id = getattr(chain, f"{role}_document_id", None)
            if document_id:
                document_ids.add(document_id)

        ordered_document_ids = sorted(document_ids)
        if ordered_document_ids:
            list(
                db.scalars(
                    select(Document.id)
                    .where(
                        Document.tenant_id == tenant_id,
                        Document.id.in_(ordered_document_ids),
                    )
                    .order_by(Document.id)
                    .with_for_update()
                )
            )
            list(
                db.scalars(
                    select(DocumentLine.id)
                    .where(
                        DocumentLine.tenant_id == tenant_id,
                        DocumentLine.document_id.in_(ordered_document_ids),
                    )
                    .order_by(DocumentLine.id)
                    .with_for_update()
                )
            )
    return True


def _finding_matches_case_contract(
    db: Session,
    *,
    case_type: str,
    finding: ProvenanceFinding,
) -> bool:
    """Require an exact P1 case→rule identity before invoking current-support verification."""
    rule_contract = _P1_RULE_MATCHERS.get(case_type)
    if rule_contract is None:
        return False
    expected_rule_id, matcher = rule_contract
    if finding.rule_id != expected_rule_id:
        return False
    return matcher(db, finding=finding)


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

    case = db.get(DiscrepancyCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        return None

    finding = db.scalar(
        select(ProvenanceFinding)
        .where(
            ProvenanceFinding.tenant_id == tenant_id,
            ProvenanceFinding.case_id == case_id,
        )
        .order_by(ProvenanceFinding.version.desc())
        .limit(1)
    )
    if finding is None or not _finding_matches_case_contract(
        db,
        case_type=case.case_type,
        finding=finding,
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
