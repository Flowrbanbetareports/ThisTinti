import copy
import json
from pathlib import Path

from scripts.validate_data_protection_evidence import SURFACES, validate


def _preparation() -> dict:
    return json.loads(
        Path("qualification/data_protection_evidence_manifest.json").read_text(encoding="utf-8")
    )


def _final() -> dict:
    data = _preparation()
    data["status"] = "EVIDENCE_COMPLETE_PENDING_QUALIFICATION_DECISION"
    candidate = data["candidate"]
    candidate.update(
        source_sha="a" * 40,
        windows_artifact="ThisTinti-1.0.0.exe",
        windows_artifact_sha256="b" * 64,
        self_hosted_artifact="ghcr.io/example/thistinti:1.0.0",
        self_hosted_digest="sha256:" + "c" * 64,
    )
    for key in data["local_edition"]:
        if key != "application_level_encryption_at_rest_claim":
            data["local_edition"][key] = True
    for key in data["self_hosted"]:
        data["self_hosted"][key] = True
    outbound = data["outbound_network"]
    outbound.update(
        observation_executed=True,
        evidence_reference="evidence/outbound-network.json",
        unexplained_destinations=[],
        silent_document_or_evidence_upload_detected=False,
    )
    outbound["observation_context"] = {
        "windows_version": "Windows 11",
        "tool_name": "approved-observer",
        "tool_version": "1",
        "started_at_utc": "2026-09-02T09:00:00Z",
        "ended_at_utc": "2026-09-02T09:15:00Z",
        "actions_exercised": ["startup", "ingestion_analysis", "restart"],
    }
    data["sensitive_surface_review"] = {name: "PASS" for name in SURFACES}
    data["independent_review"].update(
        security_review_reference="SEC-REPORT-1",
        privacy_legal_claims_review_reference="LEGAL-REPORT-1",
        release_blocking_findings_open=False,
    )
    return data


def test_preparation_manifest_is_valid_but_not_a_pass():
    assert validate(_preparation(), final=False) == []


def test_complete_structure_is_valid_but_validator_does_not_declare_pass():
    data = _final()
    assert data["qualification_decision"] == "NOT_A_PASS"
    assert validate(data, final=True) == []


def test_final_rejects_legacy_release_identity():
    data = _final()
    data["candidate"]["release_version"] = "3.4.0-alpha.7-rc.15"
    data["candidate"]["release_tag"] = "v3.4.0-alpha.7-rc.15"
    errors = validate(data, final=True)
    assert any("release_version" in error for error in errors)
    assert any("release_tag" in error for error in errors)


def test_final_rejects_unexplained_destination_and_silent_upload():
    data = _final()
    data["outbound_network"]["unexplained_destinations"] = ["203.0.113.8:443"]
    data["outbound_network"]["silent_document_or_evidence_upload_detected"] = True
    errors = validate(data, final=True)
    assert any("unexplained_destinations" in error for error in errors)
    assert any("silent document/evidence upload" in error for error in errors)


def test_final_rejects_incomplete_observation_context():
    data = _final()
    data["outbound_network"]["observation_context"]["actions_exercised"] = ["startup"]
    data["outbound_network"]["observation_context"]["tool_version"] = None
    errors = validate(data, final=True)
    assert any("tool_version" in error for error in errors)
    assert any("startup, ingestion_analysis and restart" in error for error in errors)


def test_final_rejects_missing_canonical_snapshot_surface_review():
    data = _final()
    del data["sensitive_surface_review"]["canonical_evidence_snapshots"]
    errors = validate(data, final=True)
    assert any("exactly the required surfaces" in error for error in errors)


def test_final_rejects_missing_independent_review_and_open_blocker():
    data = _final()
    data["independent_review"]["security_review_reference"] = None
    data["independent_review"]["release_blocking_findings_open"] = True
    errors = validate(data, final=True)
    assert any("security review #134" in error for error in errors)
    assert any("release_blocking_findings_open" in error for error in errors)


def test_validator_refuses_self_declared_qualification_pass():
    data = _final()
    data["qualification_decision"] = "PASS"
    assert any("cannot itself declare qualification PASS" in error for error in validate(data, final=True))


def test_final_rejects_application_level_encryption_claim_shortcut():
    data = _final()
    data["local_edition"]["application_level_encryption_at_rest_claim"] = True
    assert any("must not claim application-level encryption" in error for error in validate(data, final=True))


def test_final_rejects_non_pass_sensitive_surface():
    data = _final()
    data = copy.deepcopy(data)
    data["sensitive_surface_review"]["backups"] = "NOT_EXECUTED"
    assert any("backups must be PASS" in error for error in validate(data, final=True))
