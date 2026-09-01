from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.finding_provenance import _direct_document_fact_is_canonical


@pytest.mark.parametrize(
    ("field_name", "fact_type", "value"),
    [
        ("number", "document.number", '"PO-100"'),
        ("currency", "document.currency", '"USD"'),
    ],
)
def test_p1_direct_document_fact_accepts_only_canonical_native_json_metadata(field_name, fact_type, value):
    document = SimpleNamespace(id="doc-1", file_hash="abc123")
    fact = SimpleNamespace(fact_type=fact_type, value_json=value)
    origin = SimpleNamespace(
        origin_type="DOCUMENT_EVIDENCE",
        document_id=document.id,
        source_ref=f"sha256:{document.file_hash}",
        source_availability="available",
        locator_status="present",
        locator_type="JSON_POINTER",
        locator_json=f'{{"pointer":"/{field_name}"}}',
        engine_id="native-json-parser",
        engine_version="1",
    )

    assert _direct_document_fact_is_canonical(
        fact=fact,
        origin=origin,
        document=document,
        field_name=field_name,
        fact_type=fact_type,
        expected_value=value,
    )


@pytest.mark.parametrize(
    ("field_name", "fact_type", "value"),
    [
        ("number", "document.number", '"PO-100"'),
        ("currency", "document.currency", '"USD"'),
    ],
)
@pytest.mark.parametrize(
    ("target", "replacement"),
    [
        ("fact.fact_type", "document.tampered"),
        ("origin.origin_type", "SYSTEM_OBSERVATION"),
        ("origin.document_id", "doc-other"),
        ("origin.source_ref", "sha256:substituted"),
        ("origin.source_availability", "missing"),
        ("origin.locator_status", "not_applicable"),
        ("origin.locator_type", "XPATH"),
        ("origin.locator_json", '{"pointer":"/other"}'),
        ("origin.engine_id", "tampered-parser"),
        ("origin.engine_version", "999"),
    ],
)
def test_p1_direct_document_fact_rejects_provenance_metadata_substitution(
    field_name,
    fact_type,
    value,
    target,
    replacement,
):
    document = SimpleNamespace(id="doc-1", file_hash="abc123")
    fact = SimpleNamespace(fact_type=fact_type, value_json=value)
    origin = SimpleNamespace(
        origin_type="DOCUMENT_EVIDENCE",
        document_id=document.id,
        source_ref=f"sha256:{document.file_hash}",
        source_availability="available",
        locator_status="present",
        locator_type="JSON_POINTER",
        locator_json=f'{{"pointer":"/{field_name}"}}',
        engine_id="native-json-parser",
        engine_version="1",
    )

    owner_name, attribute = target.split(".", 1)
    owner = fact if owner_name == "fact" else origin
    setattr(owner, attribute, replacement)

    assert not _direct_document_fact_is_canonical(
        fact=fact,
        origin=origin,
        document=document,
        field_name=field_name,
        fact_type=fact_type,
        expected_value=value,
    )
