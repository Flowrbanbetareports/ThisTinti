from copy import deepcopy

from scripts.validate_human_campaign import ISSUE94_CRITERIA, validate


def _final_manifest():
    sessions = []
    observations = []
    for index in range(10):
        session_id = f"H-{index + 1:04d}"
        sessions.append(
            {
                "session_id": session_id,
                "prior_this_tinti_experience": "NONE",
                "purpose_explained_correctly": index < 8,
                "reached_first_evidence_backed_item": index < 8,
                "within_protocol_target": index < 8,
                "blocking_assistance": index >= 8,
                "serious_interpretation_failure": False,
                "observer_id": "OBS-CUSTODIAN",
                "evidence_refs": [f"evidence/{session_id}.json"],
            }
        )
    observations.extend(
        [
            {
                "observation_id": "OBS-KBD",
                "session_id": "H-0001",
                "issue_94_criterion": "keyboard_only_human",
                "result": "PASS",
                "observation_mode": "HUMAN",
                "evidence_refs": ["evidence/keyboard.json"],
            },
            {
                "observation_id": "OBS-AT",
                "session_id": "H-0002",
                "issue_94_criterion": "assistive_technology_human",
                "result": "PASS",
                "observation_mode": "HUMAN",
                "assistive_technology": "NVDA <record real version>",
                "evidence_refs": ["evidence/assistive-tech.json"],
            },
        ]
    )
    return {
        "schema": "thistinti-human-campaign-v1",
        "state": "EXECUTED",
        "candidate": {
            "source_sha": "a" * 40,
            "release_version": "1.0.0",
            "artifact_id": "windows-installer",
            "artifact_sha256": "b" * 64,
            "environment": "Windows clean test host",
        },
        "sessions": sessions,
        "observations": observations,
        "issue_32": {
            "untrained_session_target": 10,
            "minimum_successes": 8,
            "successes": 8,
            "result": "PASS",
        },
        "issue_94": {
            "criteria": {criterion: "PASS" for criterion in ISSUE94_CRITERIA},
            "not_applicable_rationales": {},
            "result": "PASS",
        },
        "findings": [],
        "final_result": "PASS",
    }


def test_preparation_template_shape_is_allowed_without_final_claim():
    data = {
        "schema": "thistinti-human-campaign-v1",
        "state": "PREPARATION_ONLY_NOT_EXECUTED",
        "candidate": {},
        "final_result": "NOT_A_PASS",
    }
    assert validate(data) == []


def test_complete_final_structure_can_validate():
    assert validate(_final_manifest(), final=True) == []


def test_final_rejects_fewer_than_ten_untrained_sessions():
    data = _final_manifest()
    data["sessions"].pop()
    errors = validate(data, final=True)
    assert any("exactly 10 untrained sessions" in error for error in errors)


def test_final_rejects_automated_keyboard_substitution():
    data = _final_manifest()
    data["observations"][0]["observation_mode"] = "AUTOMATED"
    errors = validate(data, final=True)
    assert any("keyboard-only PASS requires a HUMAN observation" in error for error in errors)


def test_final_rejects_assistive_technology_without_tool_identity():
    data = _final_manifest()
    data["observations"][1]["assistive_technology"] = None
    errors = validate(data, final=True)
    assert any("assistive-technology PASS requires HUMAN observation" in error for error in errors)


def test_final_rejects_stale_or_nonofficial_candidate_identity():
    data = _final_manifest()
    data["candidate"]["source_sha"] = "short"
    data["candidate"]["release_version"] = "3.4.0-alpha.7-rc.15"
    errors = validate(data, final=True)
    assert any("40-hex" in error for error in errors)
    assert any("release_version must be 1.0.0" in error for error in errors)


def test_final_rejects_not_run_criterion():
    data = _final_manifest()
    data["issue_94"]["criteria"]["diagnostics_json"] = "NOT_RUN"
    errors = validate(data, final=True)
    assert any("diagnostics_json is not complete" in error for error in errors)


def test_final_requires_rationale_for_not_applicable():
    data = _final_manifest()
    data["issue_94"]["criteria"]["update_backup_restore_uninstall"] = "NOT_APPLICABLE"
    errors = validate(data, final=True)
    assert any("needs NOT_APPLICABLE rationale" in error for error in errors)


def test_final_rejects_open_blocking_human_finding():
    data = _final_manifest()
    data["findings"] = [
        {
            "finding_id": "HUMAN-001",
            "qualification_impact": "BLOCKER",
            "status": "OPEN",
        }
    ]
    errors = validate(data, final=True)
    assert any("open blocking finding" in error for error in errors)


def test_success_count_is_derived_not_trusted():
    data = deepcopy(_final_manifest())
    data["issue_32"]["successes"] = 10
    errors = validate(data, final=True)
    assert any("does not match session-derived successes" in error for error in errors)
