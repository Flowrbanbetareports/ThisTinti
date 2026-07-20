from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent


def test_audit_hash_chain_detects_tampering(client, auth):
    valid = client.get("/api/audit/verify", headers=auth)
    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["events"] >= 1

    with SessionLocal() as db:
        first = db.scalar(select(AuditEvent).order_by(AuditEvent.created_at.asc()))
        first.payload_json = '{"tampered":true}'
        db.commit()

    invalid = client.get("/api/audit/verify", headers=auth)
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert invalid.json()["invalid_event_id"] is not None


def test_audit_events_form_a_continuous_chain(client, auth):
    client.get("/api/dashboard", headers=auth)
    client.post(
        "/api/users",
        headers=auth,
        json={"email": "audit@example.com", "password": "AuditPassword123!", "role": "viewer"},
    )
    events = client.get("/api/audit", headers=auth).json()
    chronological = list(reversed(events))
    previous = None
    for event in chronological:
        assert event["previous_hash"] == previous
        assert len(event["event_hash"]) == 64
        previous = event["event_hash"]
    assert client.get("/api/audit/verify", headers=auth).json()["valid"] is True
