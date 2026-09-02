from copy import deepcopy

from scripts.validate_controlled_rollout import validate


SHA = "a" * 40
ARTIFACT = "b" * 64


def final_record():
    return {
        "schema": "thistinti-controlled-rollout",
        "schema_version": 1,
        "status": "CONTROLLED_ROLLOUT_COMPLETE",
        "release_version": "1.0.0",
        "release_tag": "v1.0.0",
        "source_sha": SHA,
        "qualified_claim": "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1",
        "scope_ref": "evidence://p1-scope",
        "authorisation_policy_ref": "evidence://authorisation-policy",
        "stop_rollback_ref": "evidence://stop-rollback",
        "artifact_sha256": [ARTIFACT],
        "sessions": [
            {
                "session_id": "rollout-001",
                "operator_id": "operator-pseudonym-1",
                "environment_ref": "evidence://environment-1",
                "workload_ref": "evidence://authorised-workload-1",
                "source_sha": SHA,
                "artifact_sha256": [ARTIFACT],
                "authorisation_status": "VERIFIED",
                "observed_by_human": True,
                "synthetic_session": False,
                "started_at": "2026-09-02T10:00:00Z",
                "ended_at": "2026-09-02T10:30:00Z",
                "operator_attestation": True,
                "evidence_ref": "evidence://rollout-session-1",
            }
        ],
        "findings": [],
        "blind_holdout_used": False,
        "release_blockers_open": [],
        "limitations": ["Bounded to P1/E1 controlled use."],
        "final_evidence_ref": "evidence://controlled-rollout-final",
        "qualification_decision": "NOT_A_PASS",
        "prepared_only_notice": "not self-certifying",
    }


def test_final_structure_accepts_only_non_self_certifying_complete_record():
    assert validate(final_record(), final=True) == []


def test_legacy_prerelease_cannot_substitute_official_version():
    data = final_record()
    data["release_version"] = "3.4.0-alpha.7-rc.15"
    data["release_tag"] = "v3.4.0-alpha.7-rc.15"
    errors = validate(data, final=True)
    assert any("release_version must be exactly 1.0.0" in error for error in errors)
    assert any("release_tag must be exactly v1.0.0" in error for error in errors)


def test_synthetic_or_unobserved_session_cannot_satisfy_rollout():
    for key, value in (("synthetic_session", True), ("observed_by_human", False), ("operator_attestation", False)):
        data = final_record()
        data["sessions"][0][key] = value
        assert validate(data, final=True)


def test_unverified_authorisation_fails_closed():
    data = final_record()
    data["sessions"][0]["authorisation_status"] = "PENDING"
    assert validate(data, final=True)


def test_stale_sha_or_unknown_artifact_fails_closed():
    data = final_record()
    data["sessions"][0]["source_sha"] = "c" * 40
    assert validate(data, final=True)

    data = final_record()
    data["sessions"][0]["artifact_sha256"] = ["d" * 64]
    assert validate(data, final=True)


def test_blind_or_holdout_material_is_never_accepted_as_rollout_input():
    data = final_record()
    data["blind_holdout_used"] = True
    assert validate(data, final=True)


def test_open_release_blocker_prevents_completion():
    data = final_record()
    data["release_blockers_open"] = ["BLOCK-1"]
    assert validate(data, final=True)


def test_blocking_finding_requires_remediation_and_retest():
    data = final_record()
    data["findings"] = [
        {
            "severity": "HIGH",
            "status": "OPEN",
            "evidence_ref": "evidence://finding-1",
            "retest_ref": None,
        }
    ]
    assert validate(data, final=True)

    data["findings"][0]["status"] = "REMEDIATED"
    assert validate(data, final=True)

    data["findings"][0]["retest_ref"] = "evidence://finding-1-retest"
    assert validate(data, final=True) == []


def test_risk_acceptance_requires_rationale_and_approver():
    data = final_record()
    data["findings"] = [
        {
            "severity": "MEDIUM",
            "status": "ACCEPTED_NON_BLOCKING",
            "evidence_ref": "evidence://finding-2",
            "rationale": None,
            "approver_ref": None,
        }
    ]
    assert validate(data, final=True)

    data["findings"][0]["rationale"] = "Does not invalidate bounded release claim."
    data["findings"][0]["approver_ref"] = "evidence://risk-approver"
    assert validate(data, final=True) == []


def test_validator_cannot_be_used_to_declare_qualification_pass():
    data = final_record()
    data["qualification_decision"] = "PASS"
    assert validate(data, final=True)


def test_duplicate_session_id_is_rejected():
    data = final_record()
    data["sessions"].append(deepcopy(data["sessions"][0]))
    assert validate(data, final=True)
