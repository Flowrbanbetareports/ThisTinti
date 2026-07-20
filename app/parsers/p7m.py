from __future__ import annotations

import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path

from .base import ParsedDocument, ParseError
from .xml_invoice import parse_xml

_MAX_EXTRACTED_BYTES = 50 * 1024 * 1024


def _extract_cms(path: Path, output: Path) -> None:
    openssl = shutil.which("openssl")
    if not openssl:
        raise ParseError("OpenSSL non disponibile: impossibile estrarre il contenuto P7M")
    attempts = (
        [openssl, "cms", "-verify", "-noverify", "-binary", "-inform", "DER", "-in", str(path), "-out", str(output)],
        [openssl, "smime", "-verify", "-noverify", "-binary", "-inform", "DER", "-in", str(path), "-out", str(output)],
    )
    errors: list[str] = []
    for command in attempts:
        output.unlink(missing_ok=True)
        try:
            # The executable path is resolved locally and all arguments are fixed/list-based.
            result = subprocess.run(  # nosec B603
                command,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ParseError("Estrazione P7M interrotta: tempo massimo superato") from exc
        if result.returncode == 0 and output.exists():
            if output.stat().st_size > _MAX_EXTRACTED_BYTES:
                output.unlink(missing_ok=True)
                raise ParseError("Contenuto P7M estratto troppo grande")
            return
        errors.append((result.stderr or result.stdout or "errore OpenSSL").strip()[:300])
    raise ParseError(f"Firma o contenuto P7M non verificabile: {' | '.join(errors)}")


def parse_p7m(path: Path, overrides: dict) -> ParsedDocument:
    with tempfile.TemporaryDirectory(prefix="thistinti-p7m-") as directory:
        extracted = Path(directory) / "signed-content"
        _extract_cms(path, extracted)
        head = extracted.read_bytes()[:512].lstrip()
        if not head.startswith(b"<"):
            raise ParseError("Il P7M è valido ma non contiene un XML FatturaPA riconoscibile")
        parsed = parse_xml(extracted, overrides)
        parsed.metadata = {
            **parsed.metadata,
            "signed_container": "CMS/PKCS#7",
            "signature_integrity_checked": True,
            "certificate_trust_checked": False,
        }
        parsed.message = (
            "Contenuto P7M estratto con verifica crittografica della firma; "
            "la catena di fiducia del certificato non è stata validata."
        )
        parsed.confidence = min(parsed.confidence, 0.98)
        return parsed
