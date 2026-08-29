from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from procurement_pilot.freeze import _validate_provenance_matrix  # noqa: E402


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _contracts(tmp_path: Path) -> tuple[Path, Path, dict, dict]:
    target = {
        "status": "approved-for-blind",
        "included_case_types": ["included_rule"],
        "excluded_case_types": [
            {"case_type": "excluded_rule", "exclusion_reason": "Deferred from this blind target."}
        ],
        "excluded_families": [],
    }
    rule_pack = {
        "schema": "thistinti.procurement-rule-pack.v2",
        "rule_pack_id": "test-pack-v2",
        "version": "0.2",
        "rule_families": [
            {"id": "test-family", "engine_case_types": ["included_rule", "excluded_rule"]}
        ],
        "blind_target": target,
        "provenance": {"matrix_ref": "matrix.json", "matrix_version": "0.2"},
    }
    matrix = {
        "schema": "thistinti.procurement-provenance-matrix.v2",
        "version": "0.2",
        "rule_pack_id": "test-pack-v2",
        "rule_pack_version": "0.2",
        "blind_target": copy.deepcopy(target),
        "families": [
            {
                "id": "test-family",
                "provenance_status": "incomplete",
                "blind_scope": "mixed",
                "case_types": ["included_rule", "excluded_rule"],
            }
        ],
        "rules": [
            {
                "family": "test-family",
                "case_type": "included_rule",
                "provenance_status": "complete",
                "blind_scope": "included",
                "blind_eligible": True,
            },
            {
                "family": "test-family",
                "case_type": "excluded_rule",
                "provenance_status": "incomplete",
                "blind_scope": "excluded",
                "blind_eligible": False,
                "exclusion_reason": "Deferred from this blind target.",
            },
        ],
        "blind_readiness": {
            "ready": True,
            "target_status": "approved-for-blind",
            "target_approved": True,
            "target_nonempty": True,
            "blocking_case_types": [],
            "unsupported_included_families": [],
        },
    }
    rule_path = tmp_path / "rule-pack.json"
    matrix_path = tmp_path / "matrix.json"
    _write(rule_path, rule_pack)
    _write(matrix_path, matrix)
    return rule_path, matrix_path, rule_pack, matrix


def test_excluded_incomplete_rule_does_not_block_approved_target(tmp_path: Path) -> None:
    rule_path, matrix_path, rule_pack, _ = _contracts(tmp_path)
    target = _validate_provenance_matrix(rule_path, "0.2", matrix_path, "0.2")
    assert target == rule_pack["blind_target"]


def test_provisional_target_cannot_freeze(tmp_path: Path) -> None:
    rule_path, matrix_path, rule_pack, matrix = _contracts(tmp_path)
    rule_pack["blind_target"]["status"] = "calibration-provisional"
    matrix["blind_target"] = copy.deepcopy(rule_pack["blind_target"])
    matrix["blind_readiness"].update(
        {"ready": False, "target_status": "calibration-provisional", "target_approved": False}
    )
    _write(rule_path, rule_pack)
    _write(matrix_path, matrix)

    with pytest.raises(ValueError, match="blind target non approvato"):
        _validate_provenance_matrix(rule_path, "0.2", matrix_path, "0.2")


def test_included_incomplete_rule_blocks_freeze(tmp_path: Path) -> None:
    rule_path, matrix_path, _, matrix = _contracts(tmp_path)
    matrix["rules"][0]["provenance_status"] = "incomplete"
    matrix["rules"][0]["blind_eligible"] = False
    matrix["blind_readiness"]["ready"] = False
    matrix["blind_readiness"]["blocking_case_types"] = ["included_rule"]
    _write(matrix_path, matrix)

    with pytest.raises(ValueError, match="included_rule"):
        _validate_provenance_matrix(rule_path, "0.2", matrix_path, "0.2")


def test_rule_pack_cli_version_must_match_internal_version(tmp_path: Path) -> None:
    rule_path, matrix_path, _, _ = _contracts(tmp_path)
    with pytest.raises(ValueError, match="Rule Pack: versione dichiarata diversa"):
        _validate_provenance_matrix(rule_path, "0.3", matrix_path, "0.2")


def test_matrix_cannot_override_normative_scope(tmp_path: Path) -> None:
    rule_path, matrix_path, _, matrix = _contracts(tmp_path)
    matrix["rules"][0]["blind_scope"] = "excluded"
    matrix["rules"][0]["blind_eligible"] = False
    _write(matrix_path, matrix)

    with pytest.raises(ValueError, match="blind_scope incoerente"):
        _validate_provenance_matrix(rule_path, "0.2", matrix_path, "0.2")


def test_target_partition_must_cover_engine_baseline_exactly(tmp_path: Path) -> None:
    rule_path, matrix_path, rule_pack, matrix = _contracts(tmp_path)
    rule_pack["blind_target"]["excluded_case_types"] = []
    matrix["blind_target"] = copy.deepcopy(rule_pack["blind_target"])
    _write(rule_path, rule_pack)
    _write(matrix_path, matrix)

    with pytest.raises(ValueError, match="non coprono esattamente"):
        _validate_provenance_matrix(rule_path, "0.2", matrix_path, "0.2")


def test_target_cannot_be_empty(tmp_path: Path) -> None:
    rule_path, matrix_path, rule_pack, matrix = _contracts(tmp_path)
    rule_pack["blind_target"]["included_case_types"] = []
    rule_pack["blind_target"]["excluded_case_types"] = [
        {"case_type": "included_rule", "exclusion_reason": "Deferred."},
        {"case_type": "excluded_rule", "exclusion_reason": "Deferred."},
    ]
    matrix["blind_target"] = copy.deepcopy(rule_pack["blind_target"])
    _write(rule_path, rule_pack)
    _write(matrix_path, matrix)

    with pytest.raises(ValueError, match="blind target vuoto"):
        _validate_provenance_matrix(rule_path, "0.2", matrix_path, "0.2")
