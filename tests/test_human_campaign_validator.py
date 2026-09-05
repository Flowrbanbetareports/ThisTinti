from copy import deepcopy

import pytest

from scripts.validate_human_campaign import CampaignError, validate


SHA = "a" * 40
HASH = "b" * 64


def session(i: int, *, untrained: bool = True, success: bool = True, keyboard: bool = False, at: bool = False, hands_on: bool = False):
    return {
        "session_id": f"H-{i:04d}",
        "candidate_source_sha": SHA,
        "artifact_sha256": HASH,
        "execution_kind": "HUMAN_OBSERVED",
        "participant_id": f"P-{i:04d}",
        "observer_id": "O-0001",
        "prior_this_tinti_experience": "NONE" if untrained else "EXPERIENCED",
        "blind_or_holdout_content_used": False,
        "issue_32": {
            "applicable": untrained,
            "explained_product_correctly": success,
            "reached_first_evidence_backed_item": success,
            "blocking_assistance": False if success else True,
            "within_protocol_target": success,
        },
        "issue_94": {
            "keyboard_only_human_pass": keyboard,
            "assistive_technology_human_pass": at,
            "assistive_technology": "NVDA" if at else None,
            "hands_on_path_human_pass": hands_on,
        },
    }


def final_manifest():
    sessions = [session(i, success=i < 8) for i in range(10)]
    sessions[0]["issue_94"].update(
        {
            "keyboard_only_human_pass": True,
            "assistive_technology_human_pass": True,
            "assistive_technology": "NVDA",
            "hands_on_path_human_pass": True,
        }
    )
    return {
        "schema": "qualified-human-campaign.v1",
        "status": "FINAL_EVIDENCE_RECORDED",
        "qualification_claim": "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1",
        "candidate": {
            "source_sha": SHA,
            "release_version": "1.0.0",
            "release_tag": "v1.0.0",
            "artifact_sha256": HASH,
            "artifact_id": "windows-installer-1.0.0",
        },
        "campaign": {
            "protocol_ref": "docs/QUALIFIED_HUMAN_CAMPAIGN.md",
            "protocol_sha256": "c" * 64,
            "sessions": sessions,
        },
        "issue_32": {"required_untrained_sessions": 10, "minimum_successes": 8, "result": "PASS"},
        "issue_94": {
            "keyboard_only_human_review": "PASS",
            "assistive_technology_human_review": "PASS",
            "hands_on_path_review": "PASS",
            "result": "PASS",
        },
        "findings": [],
        "qualification_decision": "NOT_A_PASS",
    }


def test_valid_final_structure_is_not_qualification_pass():
    assert validate(final_manifest(), final=True) == "VALID_STRUCTURE_NOT_QUALIFICATION_PASS"


def test_legacy_release_line_cannot_replace_official_1_0():
    data = final_manifest()
    data["candidate"]["release_version"] = "3.4.0-alpha.7-rc.13"
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_automated_session_cannot_count_as_human_evidence():
    data = final_manifest()
    data["campaign"]["sessions"][0]["execution_kind"] = "AUTOMATED"
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_experienced_participant_cannot_be_counted_toward_32():
    data = final_manifest()
    data["campaign"]["sessions"][0]["prior_this_tinti_experience"] = "EXPERIENCED"
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_mixed_candidate_session_is_rejected():
    data = final_manifest()
    data["campaign"]["sessions"][2]["candidate_source_sha"] = "d" * 40
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_blind_or_holdout_content_is_forbidden():
    data = final_manifest()
    data["campaign"]["sessions"][1]["blind_or_holdout_content_used"] = True
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_32_pass_requires_full_ten_session_sample():
    data = final_manifest()
    data["campaign"]["sessions"] = data["campaign"]["sessions"][:8]
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_94_at_pass_requires_named_human_at_session():
    data = final_manifest()
    data["campaign"]["sessions"][0]["issue_94"]["assistive_technology"] = None
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_serious_open_finding_blocks_structural_completion():
    data = final_manifest()
    data["findings"] = [{"severity": "HIGH", "status": "OPEN"}]
    with pytest.raises(CampaignError):
        validate(data, final=True)


def test_validator_refuses_self_declared_qualification_pass():
    data = final_manifest()
    data["qualification_decision"] = "PASS"
    with pytest.raises(CampaignError):
        validate(data, final=True)
