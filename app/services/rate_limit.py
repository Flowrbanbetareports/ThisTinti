from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import utcnow


def consume_rate_limit(
    db: Session,
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Atomically consume one fixed-window allowance.

    The counter is intentionally global rather than tenant-scoped because it is
    used before authentication for login and upload abuse protection.
    """
    if limit < 1 or window_seconds < 1:
        raise ValueError("Rate limit and window must be positive")
    normalized_key = key[:255]
    now = utcnow()
    expires_at = now + timedelta(seconds=window_seconds)
    dialect = db.bind.dialect.name if db.bind is not None else ""

    if dialect == "postgresql":
        result = db.execute(
            text(
                """
                INSERT INTO rate_limit_counters AS current
                    (key, window_started_at, expires_at, count)
                VALUES (:key, :now, :expires_at, 1)
                ON CONFLICT (key) DO UPDATE SET
                    window_started_at = CASE
                        WHEN current.expires_at <= :now THEN :now
                        ELSE current.window_started_at
                    END,
                    expires_at = CASE
                        WHEN current.expires_at <= :now THEN :expires_at
                        ELSE current.expires_at
                    END,
                    count = CASE
                        WHEN current.expires_at <= :now THEN 1
                        ELSE current.count + 1
                    END
                RETURNING count
                """
            ),
            {"key": normalized_key, "now": now, "expires_at": expires_at},
        )
    elif dialect == "sqlite":
        result = db.execute(
            text(
                """
                INSERT INTO rate_limit_counters
                    (key, window_started_at, expires_at, count)
                VALUES (:key, :now, :expires_at, 1)
                ON CONFLICT(key) DO UPDATE SET
                    window_started_at = CASE
                        WHEN rate_limit_counters.expires_at <= :now THEN :now
                        ELSE rate_limit_counters.window_started_at
                    END,
                    expires_at = CASE
                        WHEN rate_limit_counters.expires_at <= :now THEN :expires_at
                        ELSE rate_limit_counters.expires_at
                    END,
                    count = CASE
                        WHEN rate_limit_counters.expires_at <= :now THEN 1
                        ELSE rate_limit_counters.count + 1
                    END
                RETURNING count
                """
            ),
            {"key": normalized_key, "now": now, "expires_at": expires_at},
        )
    else:
        raise RuntimeError(f"Unsupported database for atomic rate limiting: {dialect or 'unknown'}")

    count = int(result.scalar_one())
    return count <= limit, count
