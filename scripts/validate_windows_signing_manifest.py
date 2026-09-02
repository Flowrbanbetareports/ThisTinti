#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDERS = {"", "TO_BE_RECORDED", "TBD", "UNKNOWN", "NOT_VERIFIED"}


def fail(errors, message):
    errors.append(message)


def validate(data, final=False):
    errors = []
    if data.get("schema") != "thistinti-windows-signing-evidence":
        fail(errors, "unexpected schema")
    if data.get("schema_version") != 1:
        fail(errors, "schema_version must be 1")
    if data.get("product_version") != "1.0.0":
        fail(errors, "product_version must be 1.0.0")
    if data.get("release_tag") != "v1.0.0":
        fail(errors, "release_tag must be v1.0.0")
    if data.get("qualification_decision") != "NOT_A_PASS":
        fail(errors, "validator input must not self-declare qualification PASS")

    sha = data.get("source_sha", "")
    if not HEX40.fullmatch(sha):
        fail(errors, "source_sha must be full lowercase 40-hex")
    if final and sha == "0" * 40:
        fail(errors, "source_sha placeholder is forbidden in final mode")

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        fail(errors, "at least one artifact is required")
        artifacts = []

    seen_roles = set()
    seen_hashes = set()
    for i, artifact in enumerate(artifacts):
        role = artifact.get("role")
        if not role:
            fail(errors, f"artifacts[{i}] missing role")
        elif role in seen_roles:
            fail(errors, f"duplicate artifact role: {role}")
        seen_roles.add(role)

        digest = artifact.get("sha256", "")
        if not HEX64.fullmatch(digest):
            fail(errors, f"artifacts[{i}].sha256 must be lowercase 64-hex")
        if final and digest == "0" * 64:
            fail(errors, f"artifacts[{i}].sha256 placeholder forbidden in final mode")
        if digest in seen_hashes:
            fail(errors, f"duplicate artifact hash: {digest}")
        seen_hashes.add(digest)

        required = artifact.get("signing_required") is True
        if final and required:
            expected = {
                "authenticode_status": "VALID",
                "timestamp_verification": "VALID",
                "powershell_verification": "VALID",
                "signtool_verification": "VALID",
            }
            for key, value in expected.items():
                if artifact.get(key) != value:
                    fail(errors, f"artifacts[{i}].{key} must be {value} in final mode")
            if artifact.get("timestamp_present") is not True:
                fail(errors, f"artifacts[{i}] must have a trusted timestamp")
            for key in (
                "filename", "publisher_subject", "certificate_thumbprint",
                "certificate_serial", "certificate_not_before", "certificate_not_after",
                "timestamp_authority", "verified_at_utc"
            ):
                if artifact.get(key) in PLACEHOLDERS or artifact.get(key) is None:
                    fail(errors, f"artifacts[{i}].{key} is incomplete")
            if not artifact.get("verification_tool_versions"):
                fail(errors, f"artifacts[{i}] missing verification tool versions")
            if not artifact.get("evidence_refs"):
                fail(errors, f"artifacts[{i}] missing evidence refs")

    controls = data.get("pipeline_controls") or {}
    if final:
        required_true = (
            "private_key_outside_repository",
            "protected_signing_environment",
            "checksums_computed_after_signing",
            "unsigned_publication_blocked",
        )
        for key in required_true:
            if controls.get(key) is not True:
                fail(errors, f"pipeline_controls.{key} must be true")
        if controls.get("untrusted_prs_receive_signing_credentials") is not False:
            fail(errors, "untrusted PRs/forks must not receive signing credentials")
        if controls.get("logs_secret_material") is not False:
            fail(errors, "pipeline logs must not expose secret material")
        if not controls.get("evidence_refs"):
            fail(errors, "pipeline control evidence refs required")

        host = data.get("clean_windows_host") or {}
        for key in ("os_edition", "os_build"):
            if host.get(key) in PLACEHOLDERS or host.get(key) is None:
                fail(errors, f"clean_windows_host.{key} must be recorded")
        if host.get("project_dev_certificate_present") is not False:
            fail(errors, "clean Windows host must not rely on a project dev certificate")
        if host.get("project_trust_store_modified") is not False:
            fail(errors, "clean Windows host trust store must not be project-modified")

        ops = data.get("certificate_operations") or {}
        if ops.get("owner_recorded") is not True:
            fail(errors, "certificate owner must be recorded")
        for key in (
            "renewal_procedure_ref",
            "revocation_procedure_ref",
            "emergency_rotation_procedure_ref",
        ):
            if ops.get(key) in PLACEHOLDERS or ops.get(key) is None:
                fail(errors, f"certificate_operations.{key} must be recorded")

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate(data, final=args.final)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("VALID_STRUCTURE_NOT_QUALIFICATION_PASS")


if __name__ == "__main__":
    main()
