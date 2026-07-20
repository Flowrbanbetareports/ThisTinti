from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.local_schema import LOCAL_SCHEMA_VERSION, VERSION_TABLE, upgrade_local_schema


def sqlite_engine(tmp_path: Path):
    return create_engine(f"sqlite:///{tmp_path / 'local.db'}", future=True)


def test_local_schema_is_created_and_idempotent(tmp_path: Path):
    engine = sqlite_engine(tmp_path)
    assert upgrade_local_schema(engine) == LOCAL_SCHEMA_VERSION
    assert upgrade_local_schema(engine) == LOCAL_SCHEMA_VERSION
    tables = set(inspect(engine).get_table_names())
    assert VERSION_TABLE in tables
    assert {"tenants", "users", "documents", "processing_jobs"}.issubset(tables)
    with engine.connect() as connection:
        assert connection.scalar(text(f"SELECT version FROM {VERSION_TABLE} WHERE id = 1")) == LOCAL_SCHEMA_VERSION


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
