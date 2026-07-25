from __future__ import annotations

import json
from typing import Any


def numeric_provenance(line: Any) -> dict[str, str]:
    """Return parser provenance while keeping RC5 rows (without metadata) compatible."""
    try:
        raw = json.loads(line.raw_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    provenance = raw.get("numeric_provenance") if isinstance(raw, dict) else None
    return provenance if isinstance(provenance, dict) else {}


def numeric_available(line: Any, field: str) -> bool:
    return numeric_provenance(line).get(field) != "missing"


def all_numeric_available(lines: list[Any], field: str) -> bool:
    return bool(lines) and all(numeric_available(line, field) for line in lines)


def numeric_or_none(line: Any, field: str):
    return getattr(line, field) if numeric_available(line, field) else None
