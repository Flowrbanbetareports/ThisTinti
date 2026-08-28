from __future__ import annotations

import json
from pathlib import Path

from app.services.procurement_provenance import procurement_provenance_matrix


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "pilot" / "procurement" / "provenance-matrix.v0.1.json"
RULE_PACK_PATH = ROOT / "pilot" / "procurement" / "rule-pack.v0.1.json"


def test_repository_matrix_is_generated_contract() -> None:
    committed = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert committed == procurement_provenance_matrix()


def test_rule_pack_and_matrix_cover_the_same_engine_rules() -> None:
    rule_pack = json.loads(RULE_PACK_PATH.read_text(encoding="utf-8"))
    matrix = procurement_provenance_matrix()
    declared = {
        (family["id"], case_type) for family in rule_pack["rule_families"] for case_type in family["engine_case_types"]
    }
    mapped = {(rule["family"], rule["case_type"]) for rule in matrix["rules"]}
    assert mapped == declared
    assert rule_pack["provenance"]["matrix_ref"] == MATRIX_PATH.name
    assert rule_pack["provenance"]["matrix_version"] == matrix["version"]
    assert rule_pack["provenance"]["complete_required_before_blind_freeze"] is True


def test_current_procurement_baseline_exposes_provenance_debt_without_overclaiming() -> None:
    matrix = procurement_provenance_matrix()
    complete = [rule["case_type"] for rule in matrix["rules"] if rule["provenance_status"] == "complete"]
    incomplete = [rule["case_type"] for rule in matrix["rules"] if rule["provenance_status"] == "incomplete"]
    unsupported = [family["id"] for family in matrix["families"] if family["provenance_status"] == "unsupported"]

    assert complete == ["duplicate_document_number"]
    assert len(incomplete) == 15
    assert unsupported == ["temporal-consistency"]
    assert matrix["blind_readiness"]["ready"] is False
    assert sorted(incomplete) == matrix["blind_readiness"]["blocking_case_types"]
    assert matrix["claim_boundary"]["engine_finding_equals_provenance_qualified_finding"] is False
    assert matrix["claim_boundary"]["incomplete_rules_may_support_blind_accuracy_claims"] is False


def test_procurement_provenance_api_requires_auth_and_returns_tenant_scoped_matrix(client, auth) -> None:
    client.cookies.clear()
    unauthenticated = client.get("/api/rc15/procurement/provenance-matrix")
    assert unauthenticated.status_code == 401

    response = client.get("/api/rc15/procurement/provenance-matrix", headers=auth)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["tenant_id"]
    assert payload["schema"] == "thistinti.procurement-provenance-matrix.v1"
    assert payload["blind_readiness"]["ready"] is False
    assert payload["rules"][0]["case_type"] == "duplicate_document_number"


def test_ui_loads_and_labels_procurement_provenance_without_claiming_blind_readiness() -> None:
    loader = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    ui = (ROOT / "app" / "static" / "procurement-provenance.js").read_text(encoding="utf-8")
    assert "loadScript('/procurement-provenance.js')" in loader
    assert "/api/rc15/procurement/provenance-matrix" in ui
    assert "Blind non pronto" in ui
    assert "Un finding prodotto dal motore non è automaticamente un finding qualificato" in ui
