from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import set_tenant_context
from .models import AuditEvent, Tenant, uid, utcnow


def _timestamp(value: datetime) -> str:
    """Stable representation across SQLite and PostgreSQL timezone handling."""
    return value.replace(tzinfo=None).isoformat(timespec="microseconds")


def _event_digest(
    *,
    event_id: str,
    tenant_id: str,
    sequence_no: int,
    actor_id: str | None,
    action: str,
    entity_type: str | None,
    entity_id: str | None,
    payload_json: str,
    previous_hash: str | None,
    created_at: datetime,
) -> str:
    canonical = json.dumps(
        {
            "id": event_id,
            "tenant_id": tenant_id,
            "sequence_no": sequence_no,
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload_json": payload_json,
            "previous_hash": previous_hash,
            "created_at": _timestamp(created_at),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def add_audit(
    db: Session,
    tenant_id: str,
    action: str,
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    set_tenant_context(db, tenant_id)
    # The tenant row is the serialization point for the tenant audit stream.
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if tenant is None:
        raise ValueError(f"Tenant {tenant_id} not found")
    previous = db.scalar(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.sequence_no.desc()).limit(1)
    )
    sequence_no = int(tenant.audit_sequence or 0) + 1
    tenant.audit_sequence = sequence_no
    event_id = uid()
    created_at = utcnow()
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
    previous_hash = previous.event_hash if previous else None
    event_hash = _event_digest(
        event_id=event_id,
        tenant_id=tenant_id,
        sequence_no=sequence_no,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload_json,
        previous_hash=previous_hash,
        created_at=created_at,
    )
    event = AuditEvent(
        id=event_id,
        tenant_id=tenant_id,
        sequence_no=sequence_no,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload_json,
        previous_hash=previous_hash,
        event_hash=event_hash,
        created_at=created_at,
    )
    db.add(event)
    db.flush()
    return event


def verify_audit_chain(db: Session, tenant_id: str) -> dict[str, Any]:
    events = list(
        db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.sequence_no.asc()))
    )
    expected_previous: str | None = None
    expected_sequence = 1
    for index, event in enumerate(events):
        expected_hash = _event_digest(
            event_id=event.id,
            tenant_id=event.tenant_id,
            sequence_no=event.sequence_no,
            actor_id=event.actor_id,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            payload_json=event.payload_json,
            previous_hash=event.previous_hash,
            created_at=event.created_at,
        )
        if (
            event.sequence_no != expected_sequence
            or event.previous_hash != expected_previous
            or event.event_hash != expected_hash
        ):
            return {
                "valid": False,
                "events": len(events),
                "invalid_index": index,
                "invalid_event_id": event.id,
                "expected_sequence": expected_sequence,
            }
        expected_previous = event.event_hash
        expected_sequence += 1
    return {
        "valid": True,
        "events": len(events),
        "invalid_index": None,
        "invalid_event_id": None,
        "expected_sequence": expected_sequence,
    }
