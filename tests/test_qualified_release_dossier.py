from copy import deepcopy

from scripts.validate_qualified_release_dossier import EXPECTED_TRACKS, validate

SHA = "1" * 40
OTHER_SHA = "2" * 40
DIGEST = "a" * 64


def semantic_rule(index: int):
    return {
        "rule_id": f"p1-rule-{index}",
        "source_sha": SHA,
        "scenarios": {
            scenario: {
                "status": "PROVEN_FAIL_CLOSED",
                "production_decision_exercised": True,
                "review_decision_persisted": True,
                "provenance_judgment_persisted": True,
                "evidence_refs": [f"run:semantic-{index}-{scenario}"],
            }
            for scenario in ("concurrent_judgment", "conflicting_judgment")
        },
    }


def final_dossier():
    return {
        "schema": "thistinti-qualified-release-dossier",
        "schema_version": 3,
        "status": "FINAL_CANDIDATE_EVIDENCE_COMPLETE",
        "release_version": "1.0.0",
        "release_tag": "v1.0.0",
        "source_sha": SHA,
        "qualified_claim": "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1",
        "required_check_policy": {
            "reference": "ruleset:evidence-ref",
            "captured_at": "2026-09-02T08:00:00Z",
            "checks": [
                {
                    "name": "CI / External Proof",
                    "source_sha": SHA,
                    "conclusion": "success",
                    "evidence_ref": "run:123",
                }
            ],
            "main_post_merge_checks": [
                {
                    "name": "P1 PostgreSQL Concurrency Evidence",
                    "source_sha": SHA,
                    "branch": "main",
                    "event": "push",
                    "conclusion": "success",
                    "evidence_ref": "run:456",
                }
            ],
            "semantic_concurrency_proof": {
                "scope_ref": "P1:frozen-six-rule-target",
                "expected_rule_count": 6,
                "rules": [semantic_rule(index) for index in range(6)],
            },
        },
        "release_artifacts": [
            {
                "name": "ThisTinti-1.0.0-Setup.exe",
                "source_sha": SHA,
                "sha256": DIGEST,
                "evidence_ref": "release:v1.0.0#asset",
            }
        ],
        "tracks": {
            name: {"status": "COMPLETE", "source_sha": SHA, "evidence_refs": [f"evidence:{name}"]}
            for name in EXPECTED_TRACKS
        },
        "change_control": {
            "material_change_since_completed_evidence": False,
            "holdout_required": False,
            "holdout_status": "NOT_REQUIRED",
            "holdout_evidence_refs": [],
        },
        "limitations": ["bounded P1/E1 claim"],
        "prepared_only_notice": "validator does not authenticate evidence",
    }


def test_structurally_complete_final_dossier_is_not_a_qualification_claim():
    assert validate(final_dossier(), final=True) == []


def test_preparation_template_cannot_pass_final_mode():
    data = final_dossier()
    data["status"] = "PREPARATION_ONLY_NOT_EXECUTED"
    data["source_sha"] = None

    errors = validate(data, final=True)

    assert any("final status" in error for error in errors)
    assert any("final source_sha" in error for error in errors)


def test_legacy_prerelease_identity_is_rejected():
    data = final_dossier()
    data["release_version"] = "3.4.0-alpha.7-rc.15"
    data["release_tag"] = "v3.4.0-alpha.7-rc.15"

    errors = validate(data, final=True)

    assert any("release_version" in error for error in errors)
    assert any("release_tag" in error for error in errors)


def test_stale_workflow_sha_is_rejected():
    data = final_dossier()
    data["required_check_policy"]["checks"][0]["source_sha"] = OTHER_SHA

    errors = validate(data, final=True)

    assert any("required_check_policy.checks[0] is not bound" in error for error in errors)


def test_concurrency_evidence_must_be_from_exact_main_sha():
    data = final_dossier()
    data["required_check_policy"]["main_post_merge_checks"][0]["source_sha"] = OTHER_SHA

    errors = validate(data, final=True)

    assert any("main_post_merge_checks[0] is not bound" in error for error in errors)


def test_pr_only_concurrency_evidence_is_rejected():
    data = final_dossier()
    check = data["required_check_policy"]["main_post_merge_checks"][0]
    check["branch"] = "qualification-c/final-evidence-dossier"
    check["event"] = "pull_request"

    errors = validate(data, final=True)

    assert any("must be recorded from branch main" in error for error in errors)
    assert any("must be recorded from a push run" in error for error in errors)


def test_missing_or_duplicate_exact_main_concurrency_check_is_rejected():
    missing = final_dossier()
    missing["required_check_policy"]["main_post_merge_checks"] = []
    assert any(
        "must contain exactly the required exact-main check set" in error
        for error in validate(missing, final=True)
    )

    duplicate = final_dossier()
    duplicate["required_check_policy"]["main_post_merge_checks"].append(
        deepcopy(duplicate["required_check_policy"]["main_post_merge_checks"][0])
    )
    assert any(
        "must contain exactly the required exact-main check set" in error
        for error in validate(duplicate, final=True)
    )


def test_failed_exact_main_concurrency_check_is_rejected():
    data = final_dossier()
    data["required_check_policy"]["main_post_merge_checks"][0]["conclusion"] = "failure"

    errors = validate(data, final=True)

    assert any("main_post_merge_checks[0] did not conclude success" in error for error in errors)


def test_green_workflow_without_semantic_concurrency_proof_is_rejected():
    data = final_dossier()
    data["required_check_policy"]["semantic_concurrency_proof"]["rules"] = []

    errors = validate(data, final=True)

    assert any("must contain exactly 6 P1 rules" in error for error in errors)


def test_semantic_concurrency_proof_must_bind_each_rule_to_final_sha():
    data = final_dossier()
    data["required_check_policy"]["semantic_concurrency_proof"]["rules"][0]["source_sha"] = OTHER_SHA

    errors = validate(data, final=True)

    assert any("semantic_concurrency_proof.rules[0] is not bound" in error for error in errors)


def test_lock_only_concurrency_test_is_rejected():
    data = final_dossier()
    scenario = data["required_check_policy"]["semantic_concurrency_proof"]["rules"][0]["scenarios"]["concurrent_judgment"]
    scenario["production_decision_exercised"] = False
    scenario["review_decision_persisted"] = False
    scenario["provenance_judgment_persisted"] = False

    errors = validate(data, final=True)

    assert any("did not exercise the production decision path" in error for error in errors)
    assert any("did not persist ReviewDecision" in error for error in errors)
    assert any("did not persist ProvenanceJudgment" in error for error in errors)


def test_unknown_or_unreferenced_judgment_currentness_is_rejected():
    data = final_dossier()
    scenario = data["required_check_policy"]["semantic_concurrency_proof"]["rules"][0]["scenarios"]["conflicting_judgment"]
    scenario["status"] = "UNKNOWN"
    scenario["evidence_refs"] = []

    errors = validate(data, final=True)

    assert any("status must be PROVEN_FAIL_CLOSED" in error for error in errors)
    assert any("has no evidence_refs" in error for error in errors)


def test_duplicate_rule_cannot_fill_six_rule_semantic_contract():
    data = final_dossier()
    rules = data["required_check_policy"]["semantic_concurrency_proof"]["rules"]
    rules[1]["rule_id"] = rules[0]["rule_id"]

    errors = validate(data, final=True)

    assert any("duplicate semantic concurrency rule_id" in error for error in errors)


def test_stale_track_sha_is_rejected():
    data = final_dossier()
    data["tracks"]["security_134"]["source_sha"] = OTHER_SHA

    errors = validate(data, final=True)

    assert any("track security_134 is not bound" in error for error in errors)


def test_incomplete_external_track_is_rejected():
    data = final_dossier()
    data["tracks"]["privacy_legal_135"] = {
        "status": "WAITING_EXTERNAL",
        "source_sha": SHA,
        "evidence_refs": [],
    }

    errors = validate(data, final=True)

    assert any("privacy_legal_135 is not COMPLETE" in error for error in errors)
    assert any("privacy_legal_135 has no evidence_refs" in error for error in errors)


def test_required_holdout_must_be_complete_and_referenced():
    data = final_dossier()
    data["change_control"]["holdout_required"] = True
    data["change_control"]["holdout_status"] = "NOT_DETERMINED"

    errors = validate(data, final=True)

    assert any("required holdout is not COMPLETE" in error for error in errors)
    assert any("required holdout has no evidence refs" in error for error in errors)


def test_artifact_digest_and_sha_are_fail_closed():
    data = deepcopy(final_dossier())
    data["release_artifacts"][0]["source_sha"] = OTHER_SHA
    data["release_artifacts"][0]["sha256"] = "not-a-digest"

    errors = validate(data, final=True)

    assert any("release_artifacts[0] is not bound" in error for error in errors)
    assert any("release_artifacts[0].sha256 invalid" in error for error in errors)
