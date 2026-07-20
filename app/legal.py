from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

LEGAL_NOTICE_VERSION = "2026-07-20-v2"
SPECIFIC_CLAUSES = ["3", "4", "5", "7", "8", "9", "10", "11", "12"]


def legal_documents(resource_root: Path) -> dict[str, Path]:
    return {
        "license": resource_root / "LICENSE",
        "terms": resource_root / "TERMS_OF_USE.md",
        "disclaimer": resource_root / "DISCLAIMER.md",
        "privacy": resource_root / "PRIVACY.md",
        "trademarks": resource_root / "TRADEMARKS.md",
    }


def legal_document_hashes(resource_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in legal_documents(resource_root).items():
        if not path.exists():
            raise FileNotFoundError(f"Documento legale mancante: {path.name}")
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def acceptance_path(data_root: Path) -> Path:
    return data_root.expanduser().resolve() / "config" / "legal-acceptance.json"


def load_acceptance(data_root: Path) -> dict[str, object] | None:
    path = acceptance_path(data_root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def has_current_acceptance(data_root: Path, resource_root: Path) -> bool:
    payload = load_acceptance(data_root)
    if not payload or payload.get("legal_notice_version") != LEGAL_NOTICE_VERSION:
        return False
    if payload.get("accepted_terms") is not True or payload.get("accepted_specific_clauses") is not True:
        return False
    try:
        return payload.get("document_hashes") == legal_document_hashes(resource_root)
    except FileNotFoundError:
        return False


def record_acceptance(data_root: Path, resource_root: Path) -> Path:
    path = acceptance_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "legal_notice_version": LEGAL_NOTICE_VERSION,
        "accepted_at": datetime.now(UTC).isoformat(),
        "accepted_terms": True,
        "accepted_specific_clauses": True,
        "specific_clauses": SPECIFIC_CLAUSES,
        "document_hashes": legal_document_hashes(resource_root),
        "storage": "local-only",
        "transmitted_to_author": False,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
