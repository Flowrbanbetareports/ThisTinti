from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest
from packaging.version import Version

from app.version import PYTHON_PACKAGE_VERSION, RELEASE_VERSION, to_python_package_version
from scripts.check_beta_readiness import build_report
from scripts.check_release_consistency import validate_release_consistency
from scripts.http_smoke import local_http_client
from scripts.release_artifact import build_distribution_identity, required_release_files
from scripts.verify_publish_candidate import REQUIRED_WORKFLOWS, validate_candidate_payloads

ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.4.0-alpha.7-rc.5"
SOURCE_COMMIT = "a" * 40
SOURCE_TREE = "b" * 40


def run_script(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_release_consistency_gate_is_green_and_read_only():
    generated = [ROOT / "docs" / "openapi.json", ROOT / "docs" / "sbom.cdx.json"]
    before = {path: path.read_bytes() for path in generated}

    assert validate_release_consistency() == []
    result = run_script("scripts/check_release_consistency.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert {path: path.read_bytes() for path in generated} == before


def test_public_and_python_package_versions_are_equivalent_and_pep440_valid():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert PYTHON_PACKAGE_VERSION == to_python_package_version(RELEASE_VERSION)
    assert pyproject["project"]["version"] == PYTHON_PACKAGE_VERSION
    assert str(Version(PYTHON_PACKAGE_VERSION)) == PYTHON_PACKAGE_VERSION


@pytest.mark.parametrize(
    "invalid",
    ["3.4.0-alpha.7", "3.4.0-rc.7", "3.4.0-alpha.x-rc.7", "3.4.0a7+rc.7"],
)
def test_python_package_version_mapping_rejects_unsupported_public_labels(invalid):
    with pytest.raises(ValueError, match="Unsupported public release version"):
        to_python_package_version(invalid)


def test_beta_readiness_accepts_the_mapped_python_package_version():
    report = build_report(require_external=False)

    assert report["internal"]["passed"] is True, report["internal"]["failures"]
    assert report["technical_beta_candidate"] is True


def test_generators_reproduce_committed_contracts_without_rewriting_them(tmp_path):
    openapi = tmp_path / "openapi.json"
    sbom = tmp_path / "sbom.cdx.json"

    openapi_result = run_script("scripts/generate_openapi.py", "--output", str(openapi))
    sbom_result = run_script("scripts/generate_sbom.py", "--output", str(sbom))

    assert openapi_result.returncode == 0, openapi_result.stdout + openapi_result.stderr
    assert sbom_result.returncode == 0, sbom_result.stdout + sbom_result.stderr
    assert openapi.read_bytes() == (ROOT / "docs" / "openapi.json").read_bytes()
    assert sbom.read_bytes() == (ROOT / "docs" / "sbom.cdx.json").read_bytes()


def test_local_http_smoke_does_not_depend_on_host_proxy(monkeypatch):
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1")
    monkeypatch.setenv("all_proxy", "socks5://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")

    with local_http_client("http://127.0.0.1:1") as client:
        assert client.base_url.host == "127.0.0.1"


def candidate_payloads() -> tuple[dict, list[dict], list[dict]]:
    run_id = 1234
    run_number = 88
    windows_run = {
        "id": run_id,
        "name": "Build Windows Free Download",
        "event": "push",
        "head_branch": "main",
        "head_sha": SOURCE_COMMIT,
        "status": "completed",
        "conclusion": "success",
        "run_number": run_number,
    }
    artifacts = [
        {
            "id": 9876,
            "name": f"ThisTinti-Windows-{run_id}-{run_number}",
            "expired": False,
            "digest": "sha256:" + ("c" * 64),
        }
    ]
    runs = [
        {
            "name": name,
            "head_sha": SOURCE_COMMIT,
            "status": "completed",
            "conclusion": "success",
        }
        for name in REQUIRED_WORKFLOWS
    ]
    return windows_run, artifacts, runs


def test_publication_candidate_requires_green_exact_commit_build():
    windows_run, artifacts, runs = candidate_payloads()

    result = validate_candidate_payloads(
        target_sha=SOURCE_COMMIT,
        windows_run_id=1234,
        windows_run=windows_run,
        artifacts=artifacts,
        workflow_runs=runs,
    )

    assert result["artifact_id"] == 9876
    assert result["target_sha"] == SOURCE_COMMIT


def test_publication_candidate_rejects_artifact_from_another_commit():
    windows_run, artifacts, runs = candidate_payloads()
    windows_run["head_sha"] = "d" * 40

    with pytest.raises(ValueError, match="does not belong"):
        validate_candidate_payloads(
            target_sha=SOURCE_COMMIT,
            windows_run_id=1234,
            windows_run=windows_run,
            artifacts=artifacts,
            workflow_runs=runs,
        )


def write_test_artifact(directory: Path) -> Path:
    directory.mkdir()
    for name in required_release_files(VERSION):
        path = directory / name
        if name in {"frozen-local-smoke.json", "installed-local-smoke.json"}:
            path.write_text('{"passed": true}\n', encoding="utf-8")
        elif name == "installer-lifecycle-smoke.json":
            path.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "baseline_installed": True,
                        "upgrade_installed": True,
                        "installed_smoke_passed": True,
                        "uninstalled": True,
                        "data_preserved": True,
                    }
                ),
                encoding="utf-8",
            )
        elif name == f"ThisTinti-Portable-{VERSION}-x64.zip":
            identity = build_distribution_identity(
                version=VERSION,
                source_commit=SOURCE_COMMIT,
                source_tree=SOURCE_TREE,
                workflow_run=1234,
                workflow_run_number=88,
                artifact_name="ThisTinti-Windows-1234-88",
            )
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("BUILD-IDENTITY.json", json.dumps(identity))
                archive.writestr("ThisTinti.exe", b"fixture")
        elif not name.endswith(".sha256"):
            path.write_bytes(f"fixture:{name}".encode())
    for stem in (
        f"ThisTinti-Setup-{VERSION}-x64.exe",
        f"ThisTinti-Portable-{VERSION}-x64.zip",
        f"ThisTinti-{VERSION}-self-hosted-source.zip",
    ):
        payload = directory / stem
        digest = hashlib.sha256(payload.read_bytes()).hexdigest()
        (directory / f"{stem}.sha256").write_text(f"{digest}  {stem}\n", encoding="ascii")

    baseline = directory.parent / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "version": VERSION,
                "tag": f"v{VERSION}",
                "release_commit": "c" * 40,
                "installer": f"ThisTinti-Setup-{VERSION}-x64.exe",
                "sha256": "d" * 64,
            }
        ),
        encoding="utf-8",
    )
    return baseline


def test_release_artifact_manifest_detects_binary_tampering(tmp_path):
    directory = tmp_path / "release"
    baseline = write_test_artifact(directory)
    create = run_script(
        "scripts/create_release_provenance.py",
        "--directory",
        str(directory),
        "--version",
        VERSION,
        "--source-commit",
        SOURCE_COMMIT,
        "--source-tree",
        SOURCE_TREE,
        "--workflow-run",
        "1234",
        "--workflow-run-number",
        "88",
        "--artifact-name",
        "ThisTinti-Windows-1234-88",
        "--baseline-manifest",
        str(baseline),
    )
    assert create.returncode == 0, create.stdout + create.stderr

    verify_arguments = (
        "scripts/verify_release_artifact.py",
        "--directory",
        str(directory),
        "--expected-version",
        VERSION,
        "--expected-commit",
        SOURCE_COMMIT,
        "--expected-tree",
        SOURCE_TREE,
    )
    verified = run_script(*verify_arguments)
    assert verified.returncode == 0, verified.stdout + verified.stderr

    (directory / f"ThisTinti-Setup-{VERSION}-x64.exe").write_bytes(b"tampered")
    rejected = run_script(*verify_arguments)
    assert rejected.returncode == 1
    assert "checksum mismatch" in rejected.stderr.lower()


def test_release_artifact_rejects_portable_from_another_source(tmp_path):
    directory = tmp_path / "release"
    baseline = write_test_artifact(directory)
    portable = directory / f"ThisTinti-Portable-{VERSION}-x64.zip"
    wrong_identity = build_distribution_identity(
        version=VERSION,
        source_commit="f" * 40,
        source_tree=SOURCE_TREE,
        workflow_run=1234,
        workflow_run_number=88,
        artifact_name="ThisTinti-Windows-1234-88",
    )
    with zipfile.ZipFile(portable, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BUILD-IDENTITY.json", json.dumps(wrong_identity))
        archive.writestr("ThisTinti.exe", b"fixture")
    digest = hashlib.sha256(portable.read_bytes()).hexdigest()
    (directory / f"{portable.name}.sha256").write_text(f"{digest}  {portable.name}\n", encoding="ascii")

    create = run_script(
        "scripts/create_release_provenance.py",
        "--directory",
        str(directory),
        "--version",
        VERSION,
        "--source-commit",
        SOURCE_COMMIT,
        "--source-tree",
        SOURCE_TREE,
        "--workflow-run",
        "1234",
        "--workflow-run-number",
        "88",
        "--artifact-name",
        "ThisTinti-Windows-1234-88",
        "--baseline-manifest",
        str(baseline),
    )

    assert create.returncode == 1
    assert "portable distribution source identity does not match" in create.stderr.lower()


def test_release_workflows_enforce_gates_and_immutable_publication():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    windows = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
    publish = (ROOT / ".github" / "workflows" / "publish-public-preview.yml").read_text(encoding="utf-8")
    windows_build = (ROOT / "installer" / "windows" / "build_windows.ps1").read_text(encoding="utf-8")

    assert "make verify" in ci
    assert "needs: source-verification" in windows
    assert "builds\\windows-upgrade-baseline.json" in windows
    assert "Get-FileHash" in windows
    assert "create_distribution_identity.py" in windows_build
    assert "BUILD-IDENTITY.json" in windows_build
    assert "VERIFY-THIS-DOWNLOAD.md" in windows_build
    assert "release-provenance.json" in windows
    assert "workflow_dispatch:" in publish
    assert "\n  push:" not in publish
    assert "verify_publish_candidate.py" in publish
    assert '--expected-commit "$TARGET_SHA"' in publish
    assert "gh attestation verify" in publish
    assert "--clobber" not in publish
    assert "Refuse tag or release replacement" in publish


def test_latest_release_records_and_upgrade_baseline_are_coherent():
    release = json.loads((ROOT / "builds" / "release-latest.json").read_text(encoding="utf-8"))
    publication = json.loads((ROOT / "builds" / "publication-latest.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "builds" / "windows-upgrade-baseline.json").read_text(encoding="utf-8"))

    published_version = release["version"]
    baseline_version = baseline["version"]

    assert published_version == publication["version"]
    assert release["release_commit"] == publication["release_commit"]
    assert any(
        asset["name"] == f"ThisTinti-Setup-{published_version}-x64.exe"
        and asset["sha256"] == release["verification"]["installer_sha256"]
        for asset in publication["assets"]
    )

    assert baseline["installer"] == f"ThisTinti-Setup-{baseline_version}-x64.exe"
    assert baseline["release_commit"] != release["release_commit"]
    assert Version(to_python_package_version(baseline_version)) < Version(to_python_package_version(published_version))
    assert Version(to_python_package_version(published_version)) <= Version(PYTHON_PACKAGE_VERSION)
