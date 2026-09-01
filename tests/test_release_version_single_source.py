from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_assignment_has_one_canonical_source() -> None:
    canonical = ROOT / "app" / "version.py"
    canonical_text = canonical.read_text(encoding="utf-8")
    assignment = re.compile(r'^RELEASE_VERSION\s*=\s*"[^"]+"\s*$', re.MULTILINE)

    assert len(assignment.findall(canonical_text)) == 1

    # Build/runtime configuration may consume the canonical version, but must
    # not create a second RELEASE_VERSION assignment of its own.
    checked_suffixes = {".py", ".ps1", ".iss", ".yml", ".yaml", ".toml"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in checked_suffixes:
            continue
        if path == canonical or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert assignment.search(text) is None, f"second canonical release version in {path.relative_to(ROOT)}"


def test_windows_installer_consumes_version_instead_of_hardcoding_it() -> None:
    installer = (ROOT / "installer" / "windows" / "ThisTinti.iss").read_text(encoding="utf-8")
    build_script = (ROOT / "installer" / "windows" / "build_windows.ps1").read_text(encoding="utf-8")

    assert "AppVersion={#MyAppVersion}" in installer
    assert "VersionInfoVersion={#MyAppFileVersion}" in installer
    assert re.search(r"^VersionInfoVersion=\d", installer, re.MULTILINE) is None

    assert 'Select-String -Path "app\\version.py"' in build_script
    assert '"/DMyAppVersion=$Version"' in build_script
    assert '"/DMyAppFileVersion=$WindowsFileVersion"' in build_script


def test_generated_release_metadata_remains_covered_by_consistency_gate() -> None:
    gate = (ROOT / "scripts" / "check_release_consistency.py").read_text(encoding="utf-8")

    for required_source in (
        "app/version.py",
        "installer/windows/ThisTinti.iss",
        "docs/openapi.json",
        "docs/sbom.cdx.json",
        "docs/evidence/beta/external-gates.json",
    ):
        assert required_source in gate

    assert "PYTHON_PACKAGE_VERSION" in gate
    assert "RELEASE_VERSION" in gate
