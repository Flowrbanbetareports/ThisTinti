from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.provenance_locators import qualified_native_json_line_pointer


def _document(*, line_count: int = 2):
    return SimpleNamespace(id="doc-1", file_hash="abc123", lines=[object() for _ in range(line_count)])


def _origin(*, pointer: str = "/lines/1/line_total", source_ref: str = "sha256:abc123"):
    return SimpleNamespace(
        origin_type="DOCUMENT_EVIDENCE",
        document_id="doc-1",
        source_ref=source_ref,
        source_availability="available",
        locator_status="present",
        locator_type="JSON_POINTER",
        engine_id="native-json-parser",
        engine_version="1",
        locator_json=json.dumps({"pointer": pointer}),
    )


def _locator(*, pointer: str = "/lines/1/line_total") -> dict[str, object]:
    return {
        "pointer": pointer,
        "locator_type": "JSON_POINTER",
        "engine_id": "native-json-parser",
        "engine_version": "1",
    }


def test_qualified_native_json_line_pointer_accepts_exact_current_evidence():
    pointer = qualified_native_json_line_pointer(
        locator=_locator(),
        origin=_origin(),
        document=_document(),
        allowed_fields={"line_total"},
    )
    assert pointer == "/lines/1/line_total"


def test_qualified_native_json_line_pointer_rejects_impossible_coordinate():
    pointer = "/lines/2/line_total"
    assert (
        qualified_native_json_line_pointer(
            locator=_locator(pointer=pointer),
            origin=_origin(pointer=pointer),
            document=_document(line_count=2),
            allowed_fields={"line_total"},
        )
        is None
    )


def test_qualified_native_json_line_pointer_rejects_stale_document_hash():
    assert (
        qualified_native_json_line_pointer(
            locator=_locator(),
            origin=_origin(source_ref="sha256:stale"),
            document=_document(),
            allowed_fields={"line_total"},
        )
        is None
    )


def test_qualified_native_json_line_pointer_rejects_origin_pointer_mismatch():
    assert (
        qualified_native_json_line_pointer(
            locator=_locator(pointer="/lines/1/line_total"),
            origin=_origin(pointer="/lines/0/line_total"),
            document=_document(),
            allowed_fields={"line_total"},
        )
        is None
    )


def test_qualified_native_json_line_pointer_rejects_wrong_field_or_shape():
    for pointer in ("/lines/1/unit_price", "/line/1/line_total", "/lines/not-a-number/line_total"):
        assert (
            qualified_native_json_line_pointer(
                locator=_locator(pointer=pointer),
                origin=_origin(pointer=pointer),
                document=_document(),
                allowed_fields={"line_total"},
            )
            is None
        )
