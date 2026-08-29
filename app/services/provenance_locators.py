from __future__ import annotations

import json
from collections.abc import Collection

from ..models import Document
from ..provenance_models import ProvenanceOrigin


def qualified_native_json_line_pointer(
    *,
    locator: dict[str, object] | None,
    origin: ProvenanceOrigin | None,
    document: Document,
    allowed_fields: Collection[str],
) -> str | None:
    """Return the exact qualified native-JSON line pointer or fail closed.

    This is intentionally stricter than a shape-only pointer check. It binds the
    locator to the current document hash and native parser contract and rejects
    impossible line coordinates before a provenance finding may use the FACT.
    """
    if locator is None or origin is None:
        return None

    pointer = str(locator.get("pointer") or "")
    parts = pointer.split("/")
    if (
        len(parts) != 4
        or parts[0] != ""
        or parts[1] != "lines"
        or not parts[2].isdigit()
        or parts[3] not in allowed_fields
    ):
        return None
    if int(parts[2]) >= len(document.lines):
        return None

    if (
        locator.get("locator_type") != "JSON_POINTER"
        or locator.get("engine_id") != "native-json-parser"
        or locator.get("engine_version") != "1"
        or origin.origin_type != "DOCUMENT_EVIDENCE"
        or origin.document_id != document.id
        or origin.source_ref != f"sha256:{document.file_hash}"
        or origin.source_availability != "available"
        or origin.locator_status != "present"
        or origin.locator_type != "JSON_POINTER"
        or origin.engine_id != "native-json-parser"
        or origin.engine_version != "1"
    ):
        return None

    try:
        origin_locator = json.loads(origin.locator_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(origin_locator, dict) or origin_locator.get("pointer") != pointer:
        return None
    return pointer
