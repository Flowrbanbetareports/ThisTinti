from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, inspect, text

LOCAL_SCHEMA_VERSION = 1
VERSION_TABLE = "thistinti_local_schema"


def _ensure_legacy_compatibility(engine: Engine) -> None:
    """Reject an existing database only when a known table lacks required columns."""
    from .db import Base
    from . import models  # noqa: F401

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    for name, table in Base.metadata.tables.items():
        if name not in existing:
            continue
        actual = {column["name"] for column in inspector.get_columns(name)}
        expected = {column.name for column in table.columns}
        missing = sorted(expected - actual)
        if missing:
            raise RuntimeError(
                f"Database locale non compatibile: la tabella '{name}' non contiene {', '.join(missing)}. "
                "Il backup pre-aggiornamento è stato conservato."
            )


def local_schema_needs_upgrade(engine: Engine | None = None) -> bool:
    if engine is None:
        from .db import engine as configured_engine

        engine = configured_engine
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not tables:
        return False
    if VERSION_TABLE not in tables:
        return True
    with engine.connect() as connection:
        current = connection.execute(
            text("SELECT version FROM thistinti_local_schema WHERE id = 1")
        ).scalar_one_or_none()
    return current is None or int(current) != LOCAL_SCHEMA_VERSION


def upgrade_local_schema(engine: Engine | None = None) -> int:
    """Create or upgrade the SQLite schema used by the self-contained edition.

    The first local schema is intentionally identical to the SQLAlchemy model
    metadata shipped in 3.3. Future local-only changes must be implemented as
    explicit, sequential migrations before incrementing LOCAL_SCHEMA_VERSION.
    """
    if engine is None:
        from .db import engine as configured_engine

        engine = configured_engine
    if engine.dialect.name != "sqlite":
        raise RuntimeError("La Local Edition supporta soltanto SQLite")

    _ensure_legacy_compatibility(engine)
    from .db import Base
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {VERSION_TABLE} (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
        )
        current = connection.execute(
            text("SELECT version FROM thistinti_local_schema WHERE id = 1")
        ).scalar_one_or_none()
        if current is not None and int(current) > LOCAL_SCHEMA_VERSION:
            raise RuntimeError(
                f"Il database usa lo schema locale {current}, più recente del programma ({LOCAL_SCHEMA_VERSION})."
            )
        # No sequential transformations are required for schema version 1.
        connection.execute(
            text(
                """
                INSERT INTO thistinti_local_schema (id, version, applied_at)
                VALUES (1, :version, :applied_at)
                ON CONFLICT(id) DO UPDATE SET
                    version = excluded.version,
                    applied_at = excluded.applied_at
                """
            ),
            {"version": LOCAL_SCHEMA_VERSION, "applied_at": datetime.now(UTC).isoformat()},
        )
    return LOCAL_SCHEMA_VERSION
