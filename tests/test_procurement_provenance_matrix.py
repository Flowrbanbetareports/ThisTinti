from __future__ import annotations

import json
from pathlib import Path

from app.services.procurement_provenance import procurement_provenance_matrix


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "pilot" / "procurement" / "provenance-matrix.v0.2.json"
RULE_PACK_PATH = ROOT / "pilot" / "procurement" / "rule-pack.v0.2.json"
LEGACY_MATRIX_PATH = ROOT / "pilot" / "procurement" / "provenance-matrix.v0.1.json"
LEGACY_RULE_PACK_PATH = ROOT / "pilot" / "procurement" / "rule-pack.v0.1.json"


def test_repository_matrix_is_generated_contract() -> None:
    committed = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert committed == procurement_provenance_matrix()


def test_v01_baseline_is_preserved_as_historical_contract() -> None:
    assert (
        json.loads(LEGACY_RULE_PACK_PATH.read_text(encoding="utf-8"))["schema"] == "thistinti.procurement-rule-pack.v1"
    )
    assert (
        json.loads(LEGACY_MATRIX_PATH.read_text(encoding="utf-8"))["schema"]
        == "thistinti.procurement-provenance-matrix.v1"
    )


def test_rule_pack_is_normative_source_for_blind_target() -> None:
    rule_pack = json.loads(RULE_PACK_PATH.read_text(encoding="utf-8"))
    matrix = procurement_provenance_matrix()
    declared = {
        (family["id"], case_type) for family in rule_pack["rule_families"] for case_type in family["engine_case_types"]
    }
    mapped = {(rule["family"], rule["case_type"]) for rule in matrix["rules"]}
    assert mapped == declared
    assert matrix["blind_target"] == rule_pack["blind_target"]
    assert rule_pack["provenance"]["matrix_ref"] == MATRIX_PATH.name
    assert rule_pack["provenance"]["matrix_version"] == matrix["version"]


def test_current_target_is_provisional_and_only_included_incomplete_rules_block() -> None:
    matrix = procurement_provenance_matrix()
    included = [rule for rule in matrix["rules"] if rule["blind_scope"] == "included"]
    excluded = [rule for rule in matrix["rules"] if rule["blind_scope"] == "excluded"]

    assert [rule["case_type"] for rule in included] == [
        "duplicate_document_number",
        "delivered_over_order",
        "invoiced_over_received",
        "currency_mismatch",
        "payment_over_invoice",
        "payment_without_invoice",
    ]
    assert len(excluded) == 10
    qualified_included = [rule["case_type"] for rule in included if rule["blind_eligible"]]
    assert qualified_included == [
        "duplicate_document_number",
        "delivered_over_order",
        "invoiced_over_received",
        "currency_mismatch",
        "payment_over_invoice",
    ]

    currency_rule = next(rule for rule in included if rule["case_type"] == "currency_mismatch")
    assert currency_rule["provenance_status"] == "complete"
    assert currency_rule["blind_eligible"] is True

    delivered_rule = next(rule for rule in included if rule["case_type"] == "delivered_over_order")
    assert delivered_rule["provenance_status"] == "complete"
    assert delivered_rule["blind_eligible"] is True

    invoiced_rule = next(rule for rule in included if rule["case_type"] == "invoiced_over_received")
    assert invoiced_rule["provenance_status"] == "complete"
    assert invoiced_rule["blind_eligible"] is True

    payment_rule = next(rule for rule in included if rule["case_type"] == "payment_over_invoice")
    assert payment_rule["provenance_status"] == "complete"
    assert payment_rule["blind_eligible"] is True

    assert matrix["blind_readiness"]["ready"] is False
    assert matrix["blind_readiness"]["target_status"] == "calibration-provisional"
    assert matrix["blind_readiness"]["blocking_case_types"] == ["payment_without_invoice"]
    assert matrix["blind_readiness"]["unsupported_included_families"] == []
    temporal = next(family for family in matrix["families"] if family["id"] == "temporal-consistency")
    assert temporal["provenance_status"] == "unsupported"
    assert temporal["blind_scope"] == "excluded"


def test_blind_eligible_is_derived_from_scope_and_provenance() -> None:
    matrix = procurement_provenance_matrix()
    for rule in matrix["rules"]:
        assert rule["blind_eligible"] is (rule["blind_scope"] == "included" and rule["provenance_status"] == "complete")


def test_procurement_provenance_api_requires_auth_and_returns_tenant_scoped_matrix(client, auth) -> None:
    client.cookies.clear()
    unauthenticated = client.get("/api/rc15/procurement/provenance-matrix")
    assert unauthenticated.status_code == 401

    response = client.get("/api/rc15/procurement/provenance-matrix", headers=auth)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["tenant_id"]
    assert payload["schema"] == "thistinti.procurement-provenance-matrix.v2"
    assert payload["blind_readiness"]["ready"] is False
    assert payload["blind_target"]["included_case_types"]


def test_ui_exposes_target_scope_and_exclusions() -> None:
    loader = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    ui = (ROOT / "app" / "static" / "procurement-provenance.js").read_text(encoding="utf-8")
    assert "loadScript('/procurement-provenance.js')" in loader
    assert "/api/rc15/procurement/provenance-matrix" in ui
    assert "Blind non pronto" in ui
    assert "Target blind" in ui
    assert "Fuori pilot" in ui
    assert "Motivo esclusione" in ui
