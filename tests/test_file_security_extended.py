from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.parsers import ParseError
from app.services.file_security import scan_file


def test_structural_scan_accepts_clean_non_executable_file(tmp_path: Path):
    path = tmp_path / "clean.json"
    path.write_text('{"ok": true}', encoding="utf-8")
    original_required = settings.require_malware_scanner
    original_command = settings.malware_scanner_command
    object.__setattr__(settings, "require_malware_scanner", False)
    object.__setattr__(settings, "malware_scanner_command", "definitely-missing-scanner")
    try:
        result = scan_file(path)
    finally:
        object.__setattr__(settings, "require_malware_scanner", original_required)
        object.__setattr__(settings, "malware_scanner_command", original_command)
    assert result.clean is True
    assert result.scanner == "structural"


def test_structural_scan_rejects_executable_header(tmp_path: Path):
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"MZ" + b"0" * 100)
    with pytest.raises(ParseError, match="eseguibili"):
        scan_file(path)


def test_required_scanner_fails_closed_when_missing(tmp_path: Path):
    path = tmp_path / "clean.pdf"
    path.write_bytes(b"%PDF-1.4\nclean")
    original_required = settings.require_malware_scanner
    original_command = settings.malware_scanner_command
    object.__setattr__(settings, "require_malware_scanner", True)
    object.__setattr__(settings, "malware_scanner_command", "definitely-missing-scanner")
    try:
        with pytest.raises(ParseError, match="obbligatorio"):
            scan_file(path)
    finally:
        object.__setattr__(settings, "require_malware_scanner", original_required)
        object.__setattr__(settings, "malware_scanner_command", original_command)


def test_external_scanner_probe_executes_clean_file(monkeypatch):
    from subprocess import CompletedProcess

    from app.services.file_security import probe_malware_scanner

    original_required = settings.require_malware_scanner
    object.__setattr__(settings, "require_malware_scanner", True)
    monkeypatch.setattr("app.config.shutil.which", lambda _command: "/usr/bin/fake-scanner")
    monkeypatch.setattr(
        "app.services.file_security.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, stdout="", stderr=""),
    )
    try:
        result = probe_malware_scanner(timeout_seconds=2)
    finally:
        object.__setattr__(settings, "require_malware_scanner", original_required)
    assert result.clean is True
    assert result.scanner == settings.malware_scanner_command


def test_external_scanner_fails_closed_on_error(monkeypatch, tmp_path: Path):
    from subprocess import CompletedProcess

    path = tmp_path / "clean.txt"
    path.write_text("clean", encoding="utf-8")
    original_required = settings.require_malware_scanner
    object.__setattr__(settings, "require_malware_scanner", True)
    monkeypatch.setattr("app.config.shutil.which", lambda _command: "/usr/bin/fake-scanner")
    monkeypatch.setattr(
        "app.services.file_security.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args[0], 2, stdout="", stderr="daemon unavailable"),
    )
    try:
        with pytest.raises(ParseError, match="non affidabile"):
            scan_file(path)
    finally:
        object.__setattr__(settings, "require_malware_scanner", original_required)
