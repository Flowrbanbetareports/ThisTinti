from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.local_schema import LOCAL_SCHEMA_VERSION, VERSION_TABLE, upgrade_local_schema
from app.models import Tenant


PROVENANCE_TABLES = {
    "provenance_derivations",
    "provenance_origins",
    "provenance_facts",
    "provenance_derivation_inputs",
    "provenance_findings",
    "provenance_finding_facts",
    "provenance_judgments",
}


def sqlite_engine(tmp_path: Path):
    return create_engine(f"sqlite:///{tmp_path / 'local.db'}", future=True)


def test_local_schema_is_created_and_idempotent(tmp_path: Path):
    engine = sqlite_engine(tmp_path)
    assert upgrade_local_schema(engine) == LOCAL_SCHEMA_VERSION
    assert upgrade_local_schema(engine) == LOCAL_SCHEMA_VERSION
    tables = set(inspect(engine).get_table_names())
    assert VERSION_TABLE in tables
    assert {"tenants", "users", "documents", "processing_jobs", "rc15_practices"}.issubset(tables)
    assert PROVENANCE_TABLES.issubset(tables)
    with engine.connect() as connection:
        assert connection.scalar(text(f"SELECT version FROM {VERSION_TABLE} WHERE id = 1")) == LOCAL_SCHEMA_VERSION


def test_v1_to_v2_is_additive_and_preserves_existing_rows(tmp_path: Path):
    engine = sqlite_engine(tmp_path)
    Tenant.__table__.create(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                CREATE TABLE {VERSION_TABLE} (
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
                INSERT INTO tenants (id, name, status, security_version, audit_sequence, created_at)
                VALUES ('legacy-tenant', 'Legacy Local', 'active', 0, 0, '2026-08-27T00:00:00+00:00')
                """
            )
        )
        connection.execute(
            text(f"INSERT INTO {VERSION_TABLE} (id, version, applied_at) VALUES (1, 1, '2026-08-27T00:00:00+00:00')")
        )

    assert upgrade_local_schema(engine) == 2
    tables = set(inspect(engine).get_table_names())
    assert PROVENANCE_TABLES.issubset(tables)
    assert "rc15_practices" in tables
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT name FROM tenants WHERE id = 'legacy-tenant'")) == "Legacy Local"
        assert connection.scalar(text(f"SELECT version FROM {VERSION_TABLE} WHERE id = 1")) == 2


def test_newer_local_database_is_rejected(tmp_path: Path):
    engine = sqlite_engine(tmp_path)
    upgrade_local_schema(engine)
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE {VERSION_TABLE} SET version = 999 WHERE id = 1"))
    with pytest.raises(RuntimeError, match="più recente"):
        upgrade_local_schema(engine)


def test_incompatible_legacy_table_is_rejected(tmp_path: Path):
    engine = sqlite_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE tenants (id TEXT PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="non compatibile"):
        upgrade_local_schema(engine)


def test_schema_upgrade_detection(tmp_path: Path):
    from app.local_schema import local_schema_needs_upgrade

    engine = sqlite_engine(tmp_path)
    assert local_schema_needs_upgrade(engine) is False
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE legacy (id INTEGER PRIMARY KEY)"))
    assert local_schema_needs_upgrade(engine) is True
    upgrade_local_schema(engine)
    assert local_schema_needs_upgrade(engine) is False
