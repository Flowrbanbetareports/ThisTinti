from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    AuditEvent,
    ChainDocument,
    DiscrepancyCase,
    Document,
    OperationChain,
    ReviewDecision,
)

ACTIVE_CASE_STATUSES = ("open", "needs_review", "confirmed")
SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
STATUS_WEIGHT = {"confirmed": 3, "needs_review": 2, "open": 1}


def _money(value: Decimal | float | int | None) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def _case_payload(item: DiscrepancyCase, reference_key: str | None = None) -> dict:
    return {
        "id": item.id,
        "chain_id": item.chain_id,
        "reference_key": reference_key,
        "case_type": item.case_type,
        "severity": item.severity,
        "status": item.status,
        "title": item.title,
        "explanation": item.explanation,
        "recommended_action": item.recommended_action,
        "amount_estimate": _money(item.amount_estimate),
        "confidence": float(item.confidence or 0),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _ordered_cases(db: Session, tenant_id: str, *, active_only: bool = False) -> list[DiscrepancyCase]:
    severity_rank = case(
        (DiscrepancyCase.severity == "critical", 4),
        (DiscrepancyCase.severity == "high", 3),
        (DiscrepancyCase.severity == "medium", 2),
        (DiscrepancyCase.severity == "low", 1),
        else_=0,
    )
    status_rank = case(
        (DiscrepancyCase.status == "confirmed", 3),
        (DiscrepancyCase.status == "needs_review", 2),
        (DiscrepancyCase.status == "open", 1),
        else_=0,
    )
    statement = (
        select(DiscrepancyCase)
        .options(selectinload(DiscrepancyCase.evidence))
        .where(DiscrepancyCase.tenant_id == tenant_id)
    )
    if active_only:
        statement = statement.where(DiscrepancyCase.status.in_(ACTIVE_CASE_STATUSES))
    return list(
        db.scalars(
            statement.order_by(
                severity_rank.desc(),
                status_rank.desc(),
                DiscrepancyCase.amount_estimate.desc(),
                DiscrepancyCase.updated_at.desc(),
            )
        )
    )


def build_practice_summaries(db: Session, tenant_id: str, *, active_only: bool = True) -> list[dict]:
    cases = _ordered_cases(db, tenant_id, active_only=active_only)
    if not cases:
        return []
    chain_ids = sorted({item.chain_id for item in cases})
    chains = list(
        db.scalars(
            select(OperationChain).where(
                OperationChain.tenant_id == tenant_id,
                OperationChain.id.in_(chain_ids),
            )
        )
    )
    chain_by_id = {item.id: item for item in chains}
    role_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for link in db.scalars(
        select(ChainDocument).where(
            ChainDocument.tenant_id == tenant_id,
            ChainDocument.chain_id.in_(chain_ids),
        )
    ):
        role_counts[link.chain_id][link.role] += 1

    grouped: dict[str, list[DiscrepancyCase]] = defaultdict(list)
    for item in cases:
        grouped[item.chain_id].append(item)

    output: list[dict] = []
    for chain_id, items in grouped.items():
        chain = chain_by_id.get(chain_id)
        ordered = sorted(
            items,
            key=lambda item: (
                SEVERITY_WEIGHT.get(item.severity, 0),
                STATUS_WEIGHT.get(item.status, 0),
                Decimal(item.amount_estimate or 0),
                item.updated_at,
            ),
            reverse=True,
        )
        amount = sum((Decimal(item.amount_estimate or 0) for item in ordered), Decimal("0"))
        output.append(
            {
                "chain_id": chain_id,
                "reference_key": chain.reference_key if chain else None,
                "chain_status": chain.status if chain else "open",
                "chain_confidence": float(chain.confidence or 0) if chain else 0.0,
                "case_count": len(ordered),
                "critical_count": sum(item.severity == "critical" for item in ordered),
                "high_count": sum(item.severity == "high" for item in ordered),
                "amount_indicative": _money(amount),
                "amount_may_overlap": len(ordered) > 1,
                "top_case": _case_payload(ordered[0], chain.reference_key if chain else None),
                "cases": [_case_payload(item, chain.reference_key if chain else None) for item in ordered],
                "documents": dict(role_counts.get(chain_id, {})),
                "updated_at": max(item.updated_at for item in ordered).isoformat(),
            }
        )
    return sorted(
        output,
        key=lambda item: (
            item["critical_count"],
            item["high_count"],
            item["amount_indicative"],
            item["updated_at"],
        ),
        reverse=True,
    )


def build_operational_overview(db: Session, tenant_id: str) -> dict:
    practices = build_practice_summaries(db, tenant_id, active_only=True)
    active_cases = [case for practice in practices for case in practice["cases"]]
    documents = int(
        db.scalar(
            select(func.count(Document.id)).where(
                Document.tenant_id == tenant_id,
                Document.archived.is_(False),
            )
        )
        or 0
    )
    incomplete_chains = int(
        db.scalar(
            select(func.count(OperationChain.id)).where(
                OperationChain.tenant_id == tenant_id,
                OperationChain.status.in_(("open", "review")),
            )
        )
        or 0
    )
    parsing_failures = int(
        db.scalar(
            select(func.count(Document.id)).where(
                Document.tenant_id == tenant_id,
                Document.parse_status == "failed",
            )
        )
        or 0
    )
    review_required_documents = int(
        db.scalar(
            select(func.count(Document.id)).where(
                Document.tenant_id == tenant_id,
                Document.parse_status == "review_required",
            )
        )
        or 0
    )
    last_event = db.scalar(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.sequence_no.desc()).limit(1)
    )
    raw_amount = sum((Decimal(str(item["amount_estimate"])) for item in active_cases), Decimal("0"))
    return {
        "metrics": {
            "documents": documents,
            "active_cases": len(active_cases),
            "critical_cases": sum(item["severity"] == "critical" for item in active_cases),
            "practices_to_review": len(practices),
            "incomplete_chains": incomplete_chains,
            "amount_indicative": _money(raw_amount),
            "amount_may_overlap": any(item["amount_may_overlap"] for item in practices),
        },
        "next_case": active_cases[0] if active_cases else None,
        "practices": practices[:12],
        "system": {
            "status": "attention" if parsing_failures else "operational",
            "parsing_failures": parsing_failures,
            "review_required_documents": review_required_documents,
            "last_event_at": last_event.created_at.isoformat() if last_event else None,
        },
    }


def build_case_history(db: Session, tenant_id: str, case_id: str) -> list[dict]:
    decisions = list(
        db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.tenant_id == tenant_id, ReviewDecision.case_id == case_id)
            .order_by(ReviewDecision.created_at.asc())
        )
    )
    return [
        {
            "id": item.id,
            "decision": item.decision,
            "note": item.note,
            "user_id": item.user_id,
            "created_at": item.created_at.isoformat(),
        }
        for item in decisions
    ]


def build_learning_suggestions(db: Session, tenant_id: str) -> list[dict]:
    cases = list(db.scalars(select(DiscrepancyCase).where(DiscrepancyCase.tenant_id == tenant_id)))
    case_by_id = {item.id: item for item in cases}
    decisions = list(
        db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.tenant_id == tenant_id)
            .order_by(ReviewDecision.created_at.asc())
        )
    )
    latest_by_case: dict[str, ReviewDecision] = {}
    for item in decisions:
        latest_by_case[item.case_id] = item
    grouped: dict[str, list[ReviewDecision]] = defaultdict(list)
    for case_id, decision in latest_by_case.items():
        case_item = case_by_id.get(case_id)
        if case_item:
            grouped[case_item.case_type].append(decision)

    suggestions: list[dict] = []
    for case_type, items in grouped.items():
        total = len(items)
        dismissed = sum(item.decision == "dismissed" for item in items)
        confirmed = sum(item.decision in {"confirmed", "resolved"} for item in items)
        if total < 5:
            continue
        dismissed_rate = dismissed / total
        if dismissed_rate >= 0.6:
            suggestions.append(
                {
                    "case_type": case_type,
                    "sample_size": total,
                    "dismissed_rate": round(dismissed_rate, 4),
                    "confirmed_rate": round(confirmed / total, 4),
                    "proposal": "Rivedere soglia o tolleranza del controllo",
                    "reason": f"{dismissed} segnalazioni su {total} sono state classificate come falsi positivi.",
                    "safe_to_automate": False,
                    "requires_human_approval": True,
                }
            )
    return sorted(suggestions, key=lambda item: (item["dismissed_rate"], item["sample_size"]), reverse=True)


def build_operational_report(db: Session, tenant_id: str) -> dict:
    overview = build_operational_overview(db, tenant_id)
    cases = _ordered_cases(db, tenant_id, active_only=False)
    decisions = list(
        db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.tenant_id == tenant_id)
            .order_by(ReviewDecision.created_at.asc())
        )
    )
    first_decision_at: dict[str, datetime] = {}
    latest_decision: dict[str, ReviewDecision] = {}
    for decision in decisions:
        first_decision_at.setdefault(decision.case_id, decision.created_at)
        latest_decision[decision.case_id] = decision

    elapsed_minutes = []
    for item in cases:
        decided_at = first_decision_at.get(item.id)
        if decided_at:
            elapsed = (decided_at - item.created_at).total_seconds() / 60
            if elapsed >= 0:
                elapsed_minutes.append(elapsed)

    latest_values = list(latest_decision.values())
    counts = {
        "confirmed": sum(item.decision == "confirmed" for item in latest_values),
        "dismissed": sum(item.decision == "dismissed" for item in latest_values),
        "needs_review": sum(item.decision == "needs_review" for item in latest_values),
        "resolved": sum(item.decision == "resolved" for item in latest_values),
    }
    return {
        "schema": "thistinti.operational-report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "current tenant, current database",
        "overview": overview,
        "review": {
            "total_cases": len(cases),
            "cases_with_decision": len(latest_values),
            "latest_decision_counts": counts,
            "false_positive_proxy": counts["dismissed"],
            "confirmed_or_resolved": counts["confirmed"] + counts["resolved"],
            "average_minutes_to_first_decision": round(mean(elapsed_minutes), 2) if elapsed_minutes else None,
        },
        "measurement_availability": {
            "manual_time_before": None,
            "assisted_time_after": None,
            "known_false_negatives": None,
            "user_score": None,
            "note": "I dati prima/dopo e i falsi negativi richiedono una sessione pilot con misurazione umana esplicita.",
        },
        "learning_suggestions": build_learning_suggestions(db, tenant_id),
        "claim_boundary": "Rapporto operativo interno; non è una certificazione di accuratezza, contabile, legale o di produzione.",
    }
