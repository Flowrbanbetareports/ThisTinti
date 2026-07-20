#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg import sql


def required(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        file_name = os.getenv(f"{name}_FILE")
        if file_name:
            try:
                value = Path(file_name).read_text(encoding="utf-8")
            except OSError as exc:
                raise RuntimeError(f"Unable to read {name} secret file: {file_name}") from exc
    value = (value or "").strip()
    if not value:
        raise RuntimeError(f"{name} or {name}_FILE is required")
    return value


def validate_role_name(value: str, variable: str) -> str:
    if not value.replace("_", "").isalnum() or not value[0].isalpha():
        raise RuntimeError(f"{variable} must be a simple SQL role name")
    return value


def ensure_login_role(cursor: psycopg.Cursor, role: str, password: str) -> None:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    identifier = sql.Identifier(role)
    password_literal = sql.Literal(password)
    if cursor.fetchone() is None:
        cursor.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}"
            ).format(identifier, password_literal)
        )
    else:
        cursor.execute(
            sql.SQL(
                "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}"
            ).format(identifier, password_literal)
        )


def main() -> int:
    admin_url = required("THISTINTI_POSTGRES_ADMIN_URL")
    owner_user = validate_role_name(
        os.getenv("THISTINTI_DB_OWNER_USER", "thistinti_owner"),
        "THISTINTI_DB_OWNER_USER",
    )
    app_user = validate_role_name(os.getenv("THISTINTI_DB_APP_USER", "thistinti_app"), "THISTINTI_DB_APP_USER")
    if owner_user == app_user:
        raise RuntimeError("Database owner and runtime roles must be different")
    owner_password = required("THISTINTI_DB_OWNER_PASSWORD")
    app_password = required("THISTINTI_DB_APP_PASSWORD")

    with (
        psycopg.connect(admin_url, autocommit=True) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT current_database()")
        database = cursor.fetchone()[0]
        ensure_login_role(cursor, owner_user, owner_password)
        ensure_login_role(cursor, app_user, app_password)

        database_identifier = sql.Identifier(database)
        owner_identifier = sql.Identifier(owner_user)
        app_identifier = sql.Identifier(app_user)

        cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database_identifier, owner_identifier))
        cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database_identifier, app_identifier))
        cursor.execute(sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(owner_identifier))
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(app_identifier))

        # Existing objects are covered for idempotent re-runs; default privileges cover future migrations.
        cursor.execute(
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(app_identifier)
        )
        cursor.execute(
            sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}").format(app_identifier)
        )
        cursor.execute(sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {}").format(app_identifier))
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(owner_identifier, app_identifier)
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}"
            ).format(owner_identifier, app_identifier)
        )
        cursor.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {}").format(
                owner_identifier, app_identifier
            )
        )

        cursor.execute(
            "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname IN (%s, %s) ORDER BY rolname",
            (owner_user, app_user),
        )
        roles = cursor.fetchall()
        if len(roles) != 2 or any(row[1] or row[2] for row in roles):
            raise RuntimeError("PostgreSQL least-privilege roles were not configured safely")

    print(f"PostgreSQL roles configured: owner={owner_user}, runtime={app_user}, database={database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
