from __future__ import annotations

import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..config import settings
from ..parsers import ParseError

EICAR_MARKER = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
EXECUTABLE_MAGIC = (b"MZ", b"\x7fELF", b"#!")


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    scanner: str
    detail: str


def _run_external_scan(path: Path, timeout_seconds: int) -> ScanResult:
    try:
        completed = subprocess.run(  # nosec B603
            [settings.malware_scanner_command, "--no-summary", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if settings.require_malware_scanner:
            raise ParseError(f"Scanner malware non operativo: {exc}") from exc
        return ScanResult(clean=True, scanner="structural", detail=f"Scanner esterno non disponibile: {exc}")
    if completed.returncode == 1:
        raise ParseError("File rifiutato dallo scanner malware")
    if completed.returncode != 0:
        if settings.require_malware_scanner:
            detail = (completed.stderr or completed.stdout or "errore sconosciuto").strip()[:500]
            raise ParseError(f"Scanner malware non affidabile: {detail}")
        return ScanResult(clean=True, scanner="structural", detail="Scanner esterno non conclusivo")
    return ScanResult(clean=True, scanner=settings.malware_scanner_command, detail="File pulito")


def probe_malware_scanner(timeout_seconds: int = 5) -> ScanResult:
    """Verify that the configured scanner can execute a clean-file scan, not only that its binary exists."""
    if not settings.malware_scanner_available:
        raise ParseError("Scanner malware obbligatorio non disponibile")
    with tempfile.NamedTemporaryFile(prefix="thistinti-scanner-probe-", suffix=".txt") as probe:
        probe.write(b"ThisTinti malware scanner readiness probe\n")
        probe.flush()
        result = _run_external_scan(Path(probe.name), max(1, timeout_seconds))
    if result.scanner == "structural":
        raise ParseError("Scanner malware esterno non operativo")
    return result


def scan_file(path: Path) -> ScanResult:
    """Apply deterministic local checks and optional external malware scanning."""
    with path.open("rb") as handle:
        head = handle.read(4096)
        if any(head.startswith(magic) for magic in EXECUTABLE_MAGIC):
            raise ParseError("Il file contiene intestazioni eseguibili non consentite")
        content = head
        while EICAR_MARKER not in content:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            content = (content[-len(EICAR_MARKER) :] + chunk) if content else chunk
        if EICAR_MARKER in content:
            raise ParseError("File rifiutato dal controllo malware")

    if not settings.malware_scanner_available:
        if settings.require_malware_scanner:
            raise ParseError("Scanner malware obbligatorio non disponibile")
        return ScanResult(clean=True, scanner="structural", detail="Controlli strutturali completati")

    return _run_external_scan(path, settings.malware_scan_timeout_seconds)
