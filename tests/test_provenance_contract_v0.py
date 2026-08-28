from __future__ import annotations

import json
from pathlib import Path


CONTRACT_PATH = Path("contracts/provenance/v0.contract.json")
EXPECTED_ORIGIN_TYPES = {
    "DOCUMENT_EVIDENCE",
    "HUMAN_ASSERTION",
    "MASTER_DATA_IMPORT",
    "SYSTEM_OBSERVATION",
    "DETERMINISTIC_DERIVATION",
    "LEGACY_ORIGIN_UNKNOWN",
}
EXPECTED_LOCATOR_TYPES = {
    "PDF_PAGE_BOX",
    "IMAGE_BOX",
    "TEXT_RANGE",
    "CSV_CELL",
    "XLSX_CELL",
    "JSON_POINTER",
    "XPATH",
}
EXPECTED_INVARIANTS = {f"PV0-{index:03d}" for index in range(1, 11)}


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_provenance_contract_is_internal_experimental_and_complete() -> None:
    contract = _contract()

    assert contract["contract_id"] == "thistinti.provenance"
    assert contract["version"] == "0.1.0"
    assert contract["status"] == "internal_experimental"
    assert set(contract["origin_types"]) == EXPECTED_ORIGIN_TYPES
    assert set(contract["locator_types"]) == EXPECTED_LOCATOR_TYPES


def test_provenance_contract_preserves_unknown_legacy_origin() -> None:
    contract = _contract()
    legacy = contract["legacy_policy"]

    assert legacy["origin_type"] == "LEGACY_ORIGIN_UNKNOWN"
    assert legacy["complete_provenance"] is False
    assert "Never invent provenance" in legacy["rule"]


def test_provenance_records_have_required_traceability_links() -> None:
    contract = _contract()

    assert {
        "fact_id",
        "fact_type",
        "value",
        "origin_type",
        "created_at",
        "version",
    } <= set(contract["fact_record"]["required"])
    assert {
        "derivation_id",
        "input_fact_ids",
        "transformation_id",
        "engine_id",
        "engine_version",
        "configuration_hash",
    } <= set(contract["derivation_record"]["required"])
    assert {
        "finding_id",
        "input_fact_ids",
        "rule_id",
        "rule_version",
        "rule_configuration_hash",
    } <= set(contract["finding_record"]["required"])
    assert {
        "judgment_id",
        "finding_id",
        "reviewer_id",
        "decision",
        "reason",
        "previous_state",
    } <= set(contract["judgment_record"]["required"])


def test_source_unavailable_and_locator_missing_are_distinct() -> None:
    contract = _contract()

    assert "missing" in contract["locator_statuses"]
    assert "available" in contract["source_availability_states"]
    assert "deleted_by_retention" in contract["source_availability_states"]
    assert contract["privacy_and_lifecycle"]["source_unavailable_must_not_be_represented_as_locator_missing"] is True


def test_contract_invariants_are_stable_and_append_only() -> None:
    contract = _contract()
    invariant_ids = {item["id"] for item in contract["invariants"]}

    assert invariant_ids == EXPECTED_INVARIANTS
    assert contract["versioning"]["correction_policy"] == "append_new_version"
    assert contract["versioning"]["history_policy"] == "never_overwrite_provenance_history"
    assert contract["versioning"]["supersession_required"] is True
