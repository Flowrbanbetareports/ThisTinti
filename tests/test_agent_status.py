from datetime import UTC, datetime, timedelta

from scripts.agent_status import LEASE_MARKER, current_leases, parse_lease_comment


def _comment(item: str, owner: str, claimed_at: datetime, expires_at: datetime, state: str, comment_id: int):
    payload = (
        "{"
        f'"item":"{item}",'
        f'"owner":"{owner}",'
        f'"claimed_at":"{claimed_at.isoformat().replace("+00:00", "Z")}",'
        f'"expires_at":"{expires_at.isoformat().replace("+00:00", "Z")}",'
        f'"state":"{state}"'
        "}"
    )
    return {"id": comment_id, "body": f"{LEASE_MARKER}\n```json\n{payload}\n```"}


def test_parse_lease_comment_ignores_unrelated_or_malformed_comments():
    assert parse_lease_comment("ordinary discussion") is None
    assert parse_lease_comment(f"{LEASE_MARKER}\nnot-json") is None


def test_latest_active_event_wins_for_item():
    now = datetime.now(UTC)
    comments = [
        _comment("issue:135", "qualification-c", now - timedelta(minutes=5), now + timedelta(minutes=20), "active", 1),
        _comment("issue:135", "qualification-c", now - timedelta(minutes=1), now + timedelta(minutes=30), "active", 2),
    ]

    leases = current_leases(comments)

    assert leases["issue:135"].comment_id == 2
    assert leases["issue:135"].owner == "qualification-c"


def test_release_event_removes_active_lease():
    now = datetime.now(UTC)
    comments = [
        _comment("issue:135", "qualification-c", now - timedelta(minutes=5), now + timedelta(minutes=20), "active", 1),
        _comment("issue:135", "qualification-c", now - timedelta(minutes=1), now - timedelta(minutes=1), "released", 2),
    ]

    assert "issue:135" not in current_leases(comments)


def test_expired_lease_does_not_block_work():
    now = datetime.now(UTC)
    comments = [
        _comment("issue:135", "qualification-c", now - timedelta(hours=1), now - timedelta(minutes=10), "active", 1)
    ]

    assert "issue:135" not in current_leases(comments)


def test_newer_claim_can_replace_expired_owner():
    now = datetime.now(UTC)
    comments = [
        _comment("issue:135", "old-agent", now - timedelta(hours=1), now - timedelta(minutes=10), "active", 1),
        _comment("issue:135", "qualification-c", now - timedelta(minutes=1), now + timedelta(minutes=40), "active", 2),
    ]

    leases = current_leases(comments)

    assert leases["issue:135"].owner == "qualification-c"
