#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse

REQUIRED = [
    "THISTINTI_PUBLIC_HOST",
    "THISTINTI_POSTGRES_ADMIN_PASSWORD",
    "THISTINTI_DB_OWNER_PASSWORD",
    "THISTINTI_DB_APP_PASSWORD",
    "THISTINTI_SECRET_KEY",
    "THISTINTI_CORS_ORIGINS",
]


def main() -> int:
    errors: list[str] = []
    for name in REQUIRED:
        value = os.getenv(name, "")
        if not value or "replace-with" in value.lower() or "example.com" in value.lower():
            errors.append(f"{name} is missing or still a placeholder")

    secrets = [os.getenv(name, "") for name in REQUIRED[1:5]]
    if any(len(value) < 32 for value in secrets):
        errors.append("All secrets/passwords must contain at least 32 characters")
    if len(set(secrets)) != len(secrets):
        errors.append("Database passwords and application secret must be independent")

    host = os.getenv("THISTINTI_PUBLIC_HOST", "")
    valid_host = re.fullmatch(r"[A-Za-z0-9.-]+", host) is not None
    if host and (urlparse("//" + host).hostname != host or not valid_host):
        errors.append("THISTINTI_PUBLIC_HOST must be a plain DNS hostname")

    origins = [value.strip() for value in os.getenv("THISTINTI_CORS_ORIGINS", "").split(",") if value.strip()]
    expected = f"https://{host}"
    if origins != [expected]:
        errors.append(f"THISTINTI_CORS_ORIGINS must be exactly {expected}")

    if errors:
        print("Staging preflight failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Staging preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
