import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_windows_signing_manifest.py"
spec = importlib.util.spec_from_file_location("signing_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def valid_manifest():
    return {
        "schema": "thistinti-windows-signing-evidence",
        "schema_version": 1,
        "qualification_scope": "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1",
        "product_version": "1.0.0",
        "release_tag": "v1.0.0",
        "source_sha": "a" * 40,
        "qualification_decision": "NOT_A_PASS",
        "clean_windows_host": {
            "os_edition": "Windows 11 Pro",
            "os_build": "26100",
            "project_dev_certificate_present": False,
            "project_trust_store_modified": False,
        },
        "pipeline_controls": {
            "private_key_outside_repository": True,
            "untrusted_prs_receive_signing_credentials": False,
            "protected_signing_environment": True,
            "logs_secret_material": False,
            "checksums_computed_after_signing": True,
            "unsigned_publication_blocked": True,
            "evidence_refs": ["evidence/pipeline.txt"],
        },
        "artifacts": [{
            "role": "installer",
            "filename": "ThisTinti-1.0.0-setup.exe",
            "sha256": "b" * 64,
            "signing_required": True,
            "authenticode_status": "VALID",
            "publisher_subject": "CN=Example Publisher",
            "certificate_thumbprint": "ABC123",
            "certificate_serial": "1234",
            "certificate_not_before": "2026-01-01T00:00:00Z",
            "certificate_not_after": "2027-01-01T00:00:00Z",
            "timestamp_present": True,
            "timestamp_authority": "Example TSA",
            "timestamp_verification": "VALID",
            "powershell_verification": "VALID",
            "signtool_verification": "VALID",
            "verification_tool_versions": ["signtool 10.x", "PowerShell 7.x"],
            "verified_at_utc": "2026-09-02T17:00:00Z",
            "evidence_refs": ["evidence/installer-signature.txt"],
        }],
        "certificate_operations": {
            "owner_recorded": True,
            "renewal_procedure_ref": "docs/renewal.md",
            "revocation_procedure_ref": "docs/revocation.md",
            "emergency_rotation_procedure_ref": "docs/rotation.md",
        },
    }


def assert_invalid(mutator):
    data = valid_manifest()
    mutator(data)
    assert validator.validate(data, final=True)


def test_structurally_complete_manifest_is_not_a_qualification_pass():
    data = valid_manifest()
    assert validator.validate(data, final=True) == []
    assert data["qualification_decision"] == "NOT_A_PASS"


def test_rejects_legacy_prerelease_identity():
    assert_invalid(lambda d: d.update(product_version="3.4.0-alpha.7-rc.15", release_tag="v3.4.0-alpha.7-rc.15"))


def test_rejects_self_declared_pass():
    assert_invalid(lambda d: d.update(qualification_decision="PASS"))


def test_rejects_unsigned_required_artifact():
    assert_invalid(lambda d: d["artifacts"][0].update(authenticode_status="NOT_VERIFIED"))


def test_rejects_missing_timestamp():
    assert_invalid(lambda d: d["artifacts"][0].update(timestamp_present=False))


def test_rejects_pre_sign_checksum_claim():
    assert_invalid(lambda d: d["pipeline_controls"].update(checksums_computed_after_signing=False))


def test_rejects_signing_credentials_on_untrusted_prs():
    assert_invalid(lambda d: d["pipeline_controls"].update(untrusted_prs_receive_signing_credentials=True))


def test_rejects_dev_certificate_trust_on_clean_host():
    assert_invalid(lambda d: d["clean_windows_host"].update(project_dev_certificate_present=True))


def test_rejects_placeholder_sha_in_final_mode():
    assert_invalid(lambda d: d.update(source_sha="0" * 40))
