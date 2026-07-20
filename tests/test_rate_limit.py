from __future__ import annotations

from app.db import SessionLocal
from app.services.rate_limit import consume_rate_limit


def test_database_rate_limit_is_shared_and_enforced():
    with SessionLocal() as db:
        outcomes = [consume_rate_limit(db, key="test:login", limit=3, window_seconds=60)[0] for _ in range(5)]
        db.commit()
    assert outcomes == [True, True, True, False, False]


def test_database_rate_limit_rejects_invalid_configuration():
    with SessionLocal() as db:
        try:
            consume_rate_limit(db, key="test", limit=0, window_seconds=60)
        except ValueError as exc:
            assert "positive" in str(exc)
        else:
            raise AssertionError("Expected invalid rate-limit settings to be rejected")


def test_middleware_uses_shared_database_counter(client, monkeypatch):
    from dataclasses import replace

    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "settings",
        replace(main_module.settings, database_rate_limiting=True),
    )
    responses = [
        client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "NotThePassword123!"},
        )
        for _ in range(13)
    ]
    assert all(response.status_code == 401 for response in responses[:12])
    assert responses[12].status_code == 429
