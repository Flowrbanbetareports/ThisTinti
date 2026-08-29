from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_blind_target_contract_documents_normative_source_and_freeze_guards() -> None:
    contract = json.loads((ROOT / "contracts" / "pilot" / "blind-target-v2.contract.json").read_text(encoding="utf-8"))
    assert contract["contract_id"] == "thistinti.procurement-blind-target"
    assert contract["normative_source"] == "pilot/procurement/rule-pack.v0.2.json"
    assert "approved-for-blind" in contract["target_statuses"]
    assert contract["versioning"]["v1_semantics_preserved"] is True
    invariant_ids = {item["id"] for item in contract["invariants"]}
    assert invariant_ids == {"BT2-001", "BT2-002", "BT2-003", "BT2-004", "BT2-005", "BT2-006", "BT2-007"}


def test_windows_bundle_contains_normative_runtime_rule_pack() -> None:
    spec = (ROOT / "installer" / "windows" / "ThisTinti.spec").read_text(encoding="utf-8")
    assert 'ROOT / "pilot" / "procurement" / "rule-pack.v0.2.json"' in spec
    assert '"pilot/procurement"' in spec


def test_protocol_uses_v02_without_rewriting_historical_v01() -> None:
    protocol = (ROOT / "docs" / "PROCUREMENT_PILOT_PROTOCOL.md").read_text(encoding="utf-8")
    assert "rule-pack.v0.2.json" in protocol
    assert "provenance-matrix.v0.2.json" in protocol
    assert "calibration-provisional" in protocol
    assert "approved-for-blind" in protocol
    assert "rule-pack.v0.1.json" in protocol
    assert "contratto storico" in protocol
