import copy
import json
from pathlib import Path

import pytest

from scripts.validate_windows_signing_evidence import SigningEvidenceError, validate_manifest

TEMPLATE = Path("docs/qualification/windows-signing-evidence.template.json")


def load_template():
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def verified_manifest():
    data = load_template()
    data["status"] = "VERIFIED"
    source_sha = "a" * 40
    thumbprint = "b" * 40
    data["candidate"] = {
        "source_sha": source_sha,
        "release_version": "1.0.0",
        "release_tag": "v1.0.0",
    }
    data["certificate"] = {
        "subject": "CN=ThisTinti Publisher",
        "publisher_name": "ThisTinti Publisher",
        "thumbprint_sha1": thumbprint,
        "serial_number": "01AB",
        "not_before": "2026-08-01T00:00:00Z",
        "not_after": "2027-08-01T00:00:00Z",
        "ownership_ref": "approval:signing-owner:v1",
    }
    data["timestamp"] = {
        "rfc3161_url": "https://timestamp.example.invalid",
        "policy_ref": "timestamp-policy:v1",
    }
    for artifact in data["artifacts"]:
        if artifact["role"] == "application_exe":
            artifact["path"] = "ThisTinti.exe"
            artifact["signed_sha256"] = "c" * 64
        else:
            artifact["path"] = "ThisTinti-Setup-1.0.0-x64.exe"
            artifact["signed_sha256"] = "d" * 64
        artifact["authenticode_status"] = "Valid"
        artifact["signer_thumbprint_sha1"] = thumbprint
        artifact["timestamp_present"] = True
        artifact["timestamp_time"] = "2026-08-30T14:00:00Z"
        artifact["powershell_evidence_ref"] = f"evidence:ps:{artifact['role']}"
        artifact["signtool_evidence_ref"] = f"evidence:signtool:{artifact['role']}"
    data["clean_windows_validation"] = {
        "performed": True,
        "environment_ref": "clean-windows:vm-2026-08-30",
        "verified_publisher": "ThisTinti Publisher",
        "install_result": "PASS",
        "uninstall_result": "PASS",
        "evidence_ref": "evidence:clean-windows:v1",
    }
    data["publication_binding"] = {
        "checksum_manifest_ref": "release:checksums:v1",
        "release_record_ref": "release:v1.0.0",
        "workflow_run_ref": "actions:windows-release:123",
        "workflow_source_sha": source_sha,
        "release_sha": source_sha,
        "release_draft": False,
        "release_prerelease": False,
    }
    data["external_gate"] = {
        "certificate_available": True,
        "signing_performed": True,
        "clean_windows_verified": True,
        "release_identity_verified": True,
        "final_candidate_verified": True,
    }
    return data


def test_preparation_template_is_only_preparation():
    data = load_template()
    validate_manifest(data)
    with pytest.raises(SigningEvidenceError, match="requires VERIFIED"):
        validate_manifest(data, final=True)


def test_verified_status_requires_final_mode():
    data = verified_manifest()
    with pytest.raises(SigningEvidenceError, match="VERIFIED requires --final"):
        validate_manifest(data)


def test_complete_verified_manifest_passes_structural_validation():
    validate_manifest(verified_manifest(), final=True)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("release_version", "3.4.0-alpha.7-rc.15", "release_version must be 1.0.0"),
        ("release_tag", "v1.0.0-qualified-p1-e1", "release_tag must be v1.0.0"),
    ],
)
def test_final_rejects_non_official_release_identity(field, value, message):
    data = verified_manifest()
    data["candidate"][field] = value
    with pytest.raises(SigningEvidenceError, match=message):
        validate_manifest(data, final=True)


@pytest.mark.parametrize("role", ["application_exe", "installer"])
def test_final_rejects_missing_required_artifact_role(role):
    data = verified_manifest()
    data["artifacts"] = [artifact for artifact in data["artifacts"] if artifact["role"] != role]
    with pytest.raises(SigningEvidenceError, match="missing required artifact roles"):
        validate_manifest(data, final=True)


def test_final_rejects_artifact_name_not_bound_to_official_release():
    data = verified_manifest()
    data["artifacts"][1]["path"] = "ThisTinti-Setup-older-x64.exe"
    with pytest.raises(SigningEvidenceError, match="official release artifact name"):
        validate_manifest(data, final=True)


def test_final_rejects_duplicate_artifact_path():
    data = verified_manifest()
    data["artifacts"][1]["role"] = "application_exe"
    data["artifacts"][1]["path"] = data["artifacts"][0]["path"].upper()
    with pytest.raises(SigningEvidenceError, match="duplicate role|duplicate path"):
        validate_manifest(data, final=True)


def test_final_rejects_unsigned_or_invalid_artifact():
    data = verified_manifest()
    data["artifacts"][0]["authenticode_status"] = "NotSigned"
    with pytest.raises(SigningEvidenceError, match="authenticode_status must be Valid"):
        validate_manifest(data, final=True)


def test_final_rejects_certificate_substitution():
    data = verified_manifest()
    data["artifacts"][0]["signer_thumbprint_sha1"] = "9" * 40
    with pytest.raises(SigningEvidenceError, match="does not match certificate thumbprint"):
        validate_manifest(data, final=True)


def test_final_rejects_missing_timestamp():
    data = verified_manifest()
    data["artifacts"][1]["timestamp_present"] = False
    with pytest.raises(SigningEvidenceError, match="timestamp_present must be true"):
        validate_manifest(data, final=True)


def test_final_rejects_timestamp_outside_certificate_validity():
    data = verified_manifest()
    data["artifacts"][0]["timestamp_time"] = "2027-08-02T00:00:00Z"
    with pytest.raises(SigningEvidenceError, match="outside certificate validity"):
        validate_manifest(data, final=True)


def test_final_rejects_stale_workflow_sha():
    data = verified_manifest()
    data["publication_binding"]["workflow_source_sha"] = "9" * 40
    with pytest.raises(SigningEvidenceError, match="stale workflow SHA"):
        validate_manifest(data, final=True)


def test_final_rejects_release_sha_not_equal_to_candidate():
    data = verified_manifest()
    data["publication_binding"]["release_sha"] = "9" * 40
    with pytest.raises(SigningEvidenceError, match="release SHA does not match"):
        validate_manifest(data, final=True)


@pytest.mark.parametrize(("field", "value"), [("release_draft", True), ("release_prerelease", True)])
def test_final_rejects_draft_or_prerelease_official_release(field, value):
    data = verified_manifest()
    data["publication_binding"][field] = value
    with pytest.raises(SigningEvidenceError, match=field):
        validate_manifest(data, final=True)


def test_final_rejects_missing_clean_windows_validation():
    data = verified_manifest()
    data["clean_windows_validation"]["performed"] = False
    with pytest.raises(SigningEvidenceError, match="performed must be true"):
        validate_manifest(data, final=True)


def test_final_rejects_publisher_not_bound_exactly_to_certificate():
    data = verified_manifest()
    data["clean_windows_validation"]["verified_publisher"] = "Tinti Publisher"
    with pytest.raises(SigningEvidenceError, match="does not match certificate publisher_name"):
        validate_manifest(data, final=True)


def test_final_rejects_unresolved_external_gate():
    data = verified_manifest()
    data["external_gate"]["release_identity_verified"] = False
    with pytest.raises(SigningEvidenceError, match="release_identity_verified must be true"):
        validate_manifest(data, final=True)


def test_final_rejects_preparation_placeholder():
    data = verified_manifest()
    data["certificate"]["ownership_ref"] = "<approval ref>"
    with pytest.raises(SigningEvidenceError, match="preparation placeholder"):
        validate_manifest(data, final=True)


def test_final_rejects_duplicate_role_even_with_distinct_path():
    data = verified_manifest()
    extra = copy.deepcopy(data["artifacts"][0])
    extra["path"] = "other.exe"
    extra["signed_sha256"] = "e" * 64
    data["artifacts"].append(extra)
    with pytest.raises(SigningEvidenceError, match="duplicate role"):
        validate_manifest(data, final=True)
