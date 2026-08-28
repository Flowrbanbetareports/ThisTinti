from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, inspect, text

LOCAL_SCHEMA_VERSION = 2
VERSION_TABLE = "thistinti_local_schema"


def _register_models() -> None:
    """Register every table owned by the Local Edition before schema inspection/creation."""
    from . import models  # noqa: F401
    from . import provenance_models  # noqa: F401
    from . import rc15_models  # noqa: F401


def _ensure_legacy_compatibility(engine: Engine) -> None:
    """Reject an existing database only when a known table lacks required columns."""
    from .db import Base

    _register_models()
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


def _current_schema_version(engine: Engine) -> int | None:
    inspector = inspect(engine)
    if VERSION_TABLE not in set(inspector.get_table_names()):
        return None
    with engine.connect() as connection:
        current = connection.execute(
            text("SELECT version FROM thistinti_local_schema WHERE id = 1")
        ).scalar_one_or_none()
    return int(current) if current is not None else None


def local_schema_needs_upgrade(engine: Engine | None = None) -> bool:
    if engine is None:
        from .db import engine as configured_engine

        engine = configured_engine
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not tables:
        return False
    current = _current_schema_version(engine)
    return current != LOCAL_SCHEMA_VERSION


def upgrade_local_schema(engine: Engine | None = None) -> int:
    """Create or upgrade the SQLite schema used by the self-contained edition.

    Schema v2 is deliberately additive: it registers the RC15 extension tables
    and the internal Provenance Contract v0 persistence tables. It changes no
    existing business columns and performs no provenance backfill.
    """
    if engine is None:
        from .db import engine as configured_engine

        engine = configured_engine
    if engine.dialect.name != "sqlite":
        raise RuntimeError("La Local Edition supporta soltanto SQLite")

    _register_models()
    current = _current_schema_version(engine)
    if current is not None and current > LOCAL_SCHEMA_VERSION:
        raise RuntimeError(
            f"Il database usa lo schema locale {current}, più recente del programma ({LOCAL_SCHEMA_VERSION})."
        )

    _ensure_legacy_compatibility(engine)
    from .db import Base

    # v1 -> v2 requires additive tables only. create_all(checkfirst) is the
    # explicit transformation: existing rows/columns are never rewritten.
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS thistinti_local_schema (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
        )
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
