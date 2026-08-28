from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DiscrepancyCase, Document, ReviewDecision, User
from ..provenance_models import (
    LOCATOR_STATUSES,
    LOCATOR_TYPES,
    ORIGIN_TYPES,
    SOURCE_AVAILABILITY_STATES,
    ProvenanceDerivation,
    ProvenanceDerivationInput,
    ProvenanceFact,
    ProvenanceFinding,
    ProvenanceFindingFact,
    ProvenanceJudgment,
    ProvenanceOrigin,
)


class ProvenanceContractError(ValueError):
    pass


def _required(value: str | None, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ProvenanceContractError(f"{field} is required")
    return normalized


def _canonical_json(value_json: str, field: str) -> str:
    try:
        parsed = json.loads(value_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProvenanceContractError(f"{field} must contain valid JSON") from exc
    return json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _same_tenant(db: Session, model, record_id: str, tenant_id: str, field: str):
    record = db.get(model, record_id)
    if record is None or record.tenant_id != tenant_id:
        raise ProvenanceContractError(f"{field} does not reference a record in the same tenant")
    return record


def _fact_records(db: Session, tenant_id: str, fact_ids: Iterable[str]) -> list[ProvenanceFact]:
    ordered = list(fact_ids)
    if not ordered:
        raise ProvenanceContractError("at least one input fact is required")
    if len(set(ordered)) != len(ordered):
        raise ProvenanceContractError("input fact ids must be unique")
    facts = list(
        db.scalars(
            select(ProvenanceFact).where(
                ProvenanceFact.tenant_id == tenant_id,
                ProvenanceFact.id.in_(ordered),
            )
        )
    )
    by_id = {fact.id: fact for fact in facts}
    if set(by_id) != set(ordered):
        raise ProvenanceContractError("every input fact must exist in the same tenant")
    return [by_id[fact_id] for fact_id in ordered]


def create_derivation(
    db: Session,
    *,
    tenant_id: str,
    input_fact_ids: Iterable[str],
    transformation_id: str,
    engine_id: str,
    engine_version: str,
    configuration_hash: str,
) -> ProvenanceDerivation:
    facts = _fact_records(db, tenant_id, input_fact_ids)
    derivation = ProvenanceDerivation(
        tenant_id=tenant_id,
        transformation_id=_required(transformation_id, "transformation_id"),
        engine_id=_required(engine_id, "engine_id"),
        engine_version=_required(engine_version, "engine_version"),
        configuration_hash=_required(configuration_hash, "configuration_hash"),
    )
    db.add(derivation)
    db.flush()
    for position, fact in enumerate(facts, start=1):
        db.add(
            ProvenanceDerivationInput(
                tenant_id=tenant_id,
                derivation_id=derivation.id,
                fact_id=fact.id,
                position=position,
            )
        )
    db.flush()
    return derivation


def create_origin(
    db: Session,
    *,
    tenant_id: str,
    origin_type: str,
    source_ref: str | None = None,
    document_id: str | None = None,
    source_availability: str | None = None,
    locator_status: str | None = None,
    locator_type: str | None = None,
    locator_json: str | None = None,
    actor_ref: str | None = None,
    actor_user_id: str | None = None,
    reason: str | None = None,
    asserted_at: datetime | None = None,
    imported_at: datetime | None = None,
    observed_at: datetime | None = None,
    engine_id: str | None = None,
    engine_version: str | None = None,
    configuration_hash: str | None = None,
    derivation_id: str | None = None,
    legacy_marker: str | None = None,
) -> ProvenanceOrigin:
    if origin_type not in ORIGIN_TYPES:
        raise ProvenanceContractError("unsupported origin_type")
    if source_availability is not None and source_availability not in SOURCE_AVAILABILITY_STATES:
        raise ProvenanceContractError("unsupported source_availability")
    if locator_status is not None and locator_status not in LOCATOR_STATUSES:
        raise ProvenanceContractError("unsupported locator_status")
    if locator_type is not None and locator_type not in LOCATOR_TYPES:
        raise ProvenanceContractError("unsupported locator_type")
    normalized_locator_json = None
    if locator_status == "present":
        if locator_type is None or locator_json is None:
            raise ProvenanceContractError("present locators require locator_type and locator_json")
        normalized_locator_json = _canonical_json(locator_json, "locator_json")
    elif locator_type is not None or locator_json is not None:
        raise ProvenanceContractError("non-present locators cannot carry locator coordinates")

    if document_id is not None:
        _same_tenant(db, Document, document_id, tenant_id, "document_id")
    if actor_user_id is not None:
        _same_tenant(db, User, actor_user_id, tenant_id, "actor_user_id")
    if derivation_id is not None:
        _same_tenant(db, ProvenanceDerivation, derivation_id, tenant_id, "derivation_id")

    if origin_type == "DOCUMENT_EVIDENCE":
        _required(source_ref, "source_ref")
        if source_availability is None or locator_status is None:
            raise ProvenanceContractError("document evidence requires source availability and locator status")
        if source_availability == "available" and document_id is None:
            raise ProvenanceContractError("available document evidence requires document_id")
    elif origin_type == "HUMAN_ASSERTION":
        _required(actor_ref, "actor_ref")
        _required(reason, "reason")
        if asserted_at is None:
            raise ProvenanceContractError("asserted_at is required for human assertions")
    elif origin_type == "MASTER_DATA_IMPORT":
        _required(source_ref, "source_ref")
        if imported_at is None:
            raise ProvenanceContractError("imported_at is required for master data imports")
    elif origin_type == "SYSTEM_OBSERVATION":
        _required(engine_id, "engine_id")
        _required(engine_version, "engine_version")
        if observed_at is None:
            raise ProvenanceContractError("observed_at is required for system observations")
    elif origin_type == "DETERMINISTIC_DERIVATION":
        if derivation_id is None:
            raise ProvenanceContractError("derivation_id is required for deterministic derivations")
    elif origin_type == "LEGACY_ORIGIN_UNKNOWN":
        _required(legacy_marker, "legacy_marker")

    origin = ProvenanceOrigin(
        tenant_id=tenant_id,
        origin_type=origin_type,
        source_ref=source_ref,
        document_id=document_id,
        source_availability=source_availability,
        locator_status=locator_status,
        locator_type=locator_type,
        locator_json=normalized_locator_json,
        actor_ref=actor_ref,
        actor_user_id=actor_user_id,
        reason=reason,
        asserted_at=asserted_at,
        imported_at=imported_at,
        observed_at=observed_at,
        engine_id=engine_id,
        engine_version=engine_version,
        configuration_hash=configuration_hash,
        derivation_id=derivation_id,
        legacy_marker=legacy_marker,
    )
    db.add(origin)
    db.flush()
    return origin


def append_fact(
    db: Session,
    *,
    tenant_id: str,
    fact_key: str,
    fact_type: str,
    value_json: str,
    origin_id: str,
    supersedes_fact_id: str | None = None,
) -> ProvenanceFact:
    _same_tenant(db, ProvenanceOrigin, origin_id, tenant_id, "origin_id")
    normalized_key = _required(fact_key, "fact_key")
    normalized_type = _required(fact_type, "fact_type")
    canonical_value = _canonical_json(value_json, "value_json")

    if supersedes_fact_id is None:
        existing = db.scalar(
            select(ProvenanceFact.id).where(
                ProvenanceFact.tenant_id == tenant_id,
                ProvenanceFact.fact_key == normalized_key,
            )
        )
        if existing is not None:
            raise ProvenanceContractError("existing facts must be superseded explicitly")
        version = 1
    else:
        previous = _same_tenant(db, ProvenanceFact, supersedes_fact_id, tenant_id, "supersedes_fact_id")
        if previous.fact_key != normalized_key:
            raise ProvenanceContractError("a fact version can only supersede the same fact_key")
        newer = db.scalar(
            select(ProvenanceFact.id).where(
                ProvenanceFact.tenant_id == tenant_id,
                ProvenanceFact.fact_key == normalized_key,
                ProvenanceFact.version > previous.version,
            )
        )
        if newer is not None:
            raise ProvenanceContractError("superseded fact is not the latest version")
        version = previous.version + 1

    fact = ProvenanceFact(
        tenant_id=tenant_id,
        fact_key=normalized_key,
        version=version,
        fact_type=normalized_type,
        value_json=canonical_value,
        origin_id=origin_id,
        supersedes_fact_id=supersedes_fact_id,
    )
    db.add(fact)
    db.flush()
    return fact


def record_finding(
    db: Session,
    *,
    tenant_id: str,
    case_id: str,
    input_fact_ids: Iterable[str],
    rule_id: str,
    rule_version: str,
    rule_configuration_hash: str,
    supersedes_finding_id: str | None = None,
) -> ProvenanceFinding:
    _same_tenant(db, DiscrepancyCase, case_id, tenant_id, "case_id")
    facts = _fact_records(db, tenant_id, input_fact_ids)
    if supersedes_finding_id is None:
        existing = db.scalar(
            select(ProvenanceFinding.id).where(
                ProvenanceFinding.tenant_id == tenant_id,
                ProvenanceFinding.case_id == case_id,
            )
        )
        if existing is not None:
            raise ProvenanceContractError("existing finding provenance must be superseded explicitly")
        version = 1
    else:
        previous = _same_tenant(db, ProvenanceFinding, supersedes_finding_id, tenant_id, "supersedes_finding_id")
        if previous.case_id != case_id:
            raise ProvenanceContractError("a finding version can only supersede the same case")
        newer = db.scalar(
            select(ProvenanceFinding.id).where(
                ProvenanceFinding.tenant_id == tenant_id,
                ProvenanceFinding.case_id == case_id,
                ProvenanceFinding.version > previous.version,
            )
        )
        if newer is not None:
            raise ProvenanceContractError("superseded finding is not the latest version")
        version = previous.version + 1

    finding = ProvenanceFinding(
        tenant_id=tenant_id,
        case_id=case_id,
        version=version,
        rule_id=_required(rule_id, "rule_id"),
        rule_version=_required(rule_version, "rule_version"),
        rule_configuration_hash=_required(rule_configuration_hash, "rule_configuration_hash"),
        supersedes_finding_id=supersedes_finding_id,
    )
    db.add(finding)
    db.flush()
    for fact in facts:
        db.add(
            ProvenanceFindingFact(
                tenant_id=tenant_id,
                finding_id=finding.id,
                fact_id=fact.id,
                role="supporting",
            )
        )
    db.flush()
    return finding


def record_judgment(
    db: Session,
    *,
    tenant_id: str,
    finding_id: str,
    review_decision_id: str,
    reviewer_ref: str,
    decision: str,
    reason: str,
    previous_state: str,
    reviewer_user_id: str | None = None,
) -> ProvenanceJudgment:
    finding = _same_tenant(db, ProvenanceFinding, finding_id, tenant_id, "finding_id")
    review = _same_tenant(db, ReviewDecision, review_decision_id, tenant_id, "review_decision_id")
    if review.case_id != finding.case_id:
        raise ProvenanceContractError("review decision and provenance finding must reference the same case")
    if review.decision != decision:
        raise ProvenanceContractError("judgment decision must match the recorded review decision")
    if reviewer_user_id is not None:
        _same_tenant(db, User, reviewer_user_id, tenant_id, "reviewer_user_id")
        if review.user_id != reviewer_user_id:
            raise ProvenanceContractError("reviewer_user_id must match the recorded review decision")

    judgment = ProvenanceJudgment(
        tenant_id=tenant_id,
        finding_id=finding_id,
        review_decision_id=review_decision_id,
        reviewer_ref=_required(reviewer_ref, "reviewer_ref"),
        reviewer_user_id=reviewer_user_id,
        decision=_required(decision, "decision"),
        reason=_required(reason, "reason"),
        previous_state=_required(previous_state, "previous_state"),
    )
    db.add(judgment)
    db.flush()
    return judgment
