"""Minimal SQLAlchemy hook for the SQLite-only Local Edition.

The server distribution remains source-based and may use PostgreSQL. The frozen
Local Edition deliberately bundles only the pysqlite dialect to reduce size and
avoid scanning unrelated dialect plugins installed on a build host.
"""

hiddenimports = [
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.base",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "sqlalchemy.sql.default_comparator",
]

excludedimports = [
    "sqlalchemy.dialects.mssql",
    "sqlalchemy.dialects.mysql",
    "sqlalchemy.dialects.oracle",
    "sqlalchemy.dialects.postgresql",
]
