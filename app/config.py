from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return _value(name, str(default)).lower() == "true"


def _value(name: str, default: str) -> str:
    direct = os.getenv(name)
    if direct is not None:
        return direct
    file_name = os.getenv(f"{name}_FILE")
    if file_name:
        path = Path(file_name)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Unable to read secret file for {name}: {path}") from exc
    return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "ThisTinti"
    environment: str = os.getenv("THISTINTI_ENV", "development").lower()
    process_role: str = os.getenv("THISTINTI_PROCESS_ROLE", "app").lower()
    local_edition: bool = _bool("THISTINTI_LOCAL_EDITION", False)
    legal_notice_version: str = _value("THISTINTI_LEGAL_NOTICE_VERSION", "2026-07-20-v2")
    self_hosted_reference: bool = _bool("THISTINTI_SELF_HOSTED_REFERENCE", False)
    operator_accepts_self_hosting_responsibility: bool = _bool(
        "THISTINTI_OPERATOR_ACCEPTS_SELF_HOSTING_RESPONSIBILITY", False
    )
    operator_accepts_no_support: bool = _bool("THISTINTI_OPERATOR_ACCEPTS_NO_SUPPORT", False)
    deployment_id: str = _value("THISTINTI_DEPLOYMENT_ID", "")
    operator_acceptance_file: Path | None = (
        Path(_value("THISTINTI_OPERATOR_ACCEPTANCE_FILE", ""))
        if _value("THISTINTI_OPERATOR_ACCEPTANCE_FILE", "")
        else None
    )
    database_url: str = _value("THISTINTI_DATABASE_URL", "sqlite:///./thistinti.db")
    storage_dir: Path = Path(os.getenv("THISTINTI_STORAGE_DIR", "./data/uploads"))
    quarantine_dir: Path = Path(os.getenv("THISTINTI_QUARANTINE_DIR", "./data/quarantine"))
    rejected_dir: Path = Path(os.getenv("THISTINTI_REJECTED_DIR", "./data/rejected"))
    secret_key: str = _value("THISTINTI_SECRET_KEY", "change-me-in-production")
    token_ttl_seconds: int = int(os.getenv("THISTINTI_TOKEN_TTL_SECONDS", "43200"))
    max_upload_mb: int = int(os.getenv("THISTINTI_MAX_UPLOAD_MB", "25"))
    max_batch_files: int = int(os.getenv("THISTINTI_MAX_BATCH_FILES", "200"))
    max_batch_expanded_mb: int = int(os.getenv("THISTINTI_MAX_BATCH_EXPANDED_MB", "250"))
    allow_registration: bool = _bool("THISTINTI_ALLOW_REGISTRATION", True)
    auto_create_schema: bool = _bool("THISTINTI_AUTO_CREATE_SCHEMA", True)
    database_rate_limiting: bool = _bool(
        "THISTINTI_DATABASE_RATE_LIMITING",
        os.getenv("THISTINTI_ENV", "development").lower() == "production",
    )
    secure_cookies: bool = _bool("THISTINTI_SECURE_COOKIES", False)
    async_ingestion_enabled: bool = _bool("THISTINTI_ASYNC_INGESTION_ENABLED", False)
    allow_synchronous_ingestion: bool = _bool(
        "THISTINTI_ALLOW_SYNCHRONOUS_INGESTION",
        os.getenv("THISTINTI_ENV", "development").lower() != "production",
    )
    worker_max_attempts: int = int(os.getenv("THISTINTI_WORKER_MAX_ATTEMPTS", "3"))
    worker_lease_seconds: int = int(os.getenv("THISTINTI_WORKER_LEASE_SECONDS", "300"))
    worker_heartbeat_stale_seconds: int = int(os.getenv("THISTINTI_WORKER_HEARTBEAT_STALE_SECONDS", "30"))
    completed_job_retention_days: int = int(os.getenv("THISTINTI_COMPLETED_JOB_RETENTION_DAYS", "30"))
    quarantine_retention_hours: int = int(os.getenv("THISTINTI_QUARANTINE_RETENTION_HOURS", "24"))
    malware_scanner_command: str = os.getenv("THISTINTI_MALWARE_SCANNER_COMMAND", "clamdscan")
    require_malware_scanner: bool = _bool(
        "THISTINTI_REQUIRE_MALWARE_SCANNER",
        os.getenv("THISTINTI_ENV", "development").lower() == "production",
    )
    malware_scan_timeout_seconds: int = int(os.getenv("THISTINTI_MALWARE_SCAN_TIMEOUT_SECONDS", "60"))
    ocr_enabled: bool = _bool("THISTINTI_OCR_ENABLED", True)
    ocr_languages: str = os.getenv("THISTINTI_OCR_LANGUAGES", "ita+eng")
    ocr_max_pages: int = int(os.getenv("THISTINTI_OCR_MAX_PAGES", "20"))
    ocr_dpi: int = int(os.getenv("THISTINTI_OCR_DPI", "200"))
    ocr_timeout_seconds: int = int(os.getenv("THISTINTI_OCR_TIMEOUT_SECONDS", "45"))
    ocr_max_chars: int = int(os.getenv("THISTINTI_OCR_MAX_CHARS", "2000000"))
    session_cookie_name: str = "thistinti_session"
    csrf_cookie_name: str = "thistinti_csrf"

    @property
    def malware_scanner_available(self) -> bool:
        return shutil.which(self.malware_scanner_command) is not None

    def operator_acceptance_errors(self) -> list[str]:
        if not self.self_hosted_reference:
            return []
        if self.operator_acceptance_file is None:
            return ["THISTINTI_OPERATOR_ACCEPTANCE_FILE is required for the self-hosted reference deployment"]
        try:
            payload = json.loads(self.operator_acceptance_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            return [f"Operator acceptance evidence is unreadable: {exc}"]
        errors: list[str] = []
        if payload.get("legal_notice_version") != self.legal_notice_version:
            errors.append("Operator acceptance legal notice version is obsolete")
        if payload.get("deployment_id") != self.deployment_id:
            errors.append("Operator acceptance deployment id does not match THISTINTI_DEPLOYMENT_ID")
        if payload.get("operator_accepts_self_hosting_responsibility") is not True:
            errors.append("Operator acceptance evidence does not record self-hosting responsibility")
        if payload.get("operator_accepts_no_guaranteed_support_or_sla") is not True:
            errors.append("Operator acceptance evidence does not record absence of guaranteed support or SLA")
        root = Path(__file__).resolve().parents[1]
        legal_files = ("LICENSE", "TERMS_OF_USE.md", "DISCLAIMER.md", "PRIVACY.md", "TRADEMARKS.md", "SUPPORT.md")
        expected = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in legal_files}
        if payload.get("legal_document_hashes") != expected:
            errors.append("Legal documents changed after operator acceptance")
        return errors

    def production_errors(self) -> list[str]:
        if self.environment != "production":
            return []
        errors: list[str] = []
        if len(self.secret_key) < 32 or any(x in self.secret_key.lower() for x in ("change-me", "replace-with")):
            errors.append("THISTINTI_SECRET_KEY must be a strong non-default secret")
        if not self.database_url.startswith("postgresql"):
            errors.append("Production requires PostgreSQL")
        if self.auto_create_schema:
            errors.append("THISTINTI_AUTO_CREATE_SCHEMA must be false in production")
        if not self.secure_cookies:
            errors.append("THISTINTI_SECURE_COOKIES must be true in production")
        if self.allow_registration:
            errors.append("Public registration must be disabled in production")
        if not self.database_rate_limiting:
            errors.append("Database-backed rate limiting must be enabled in production")
        if not self.async_ingestion_enabled:
            errors.append("Asynchronous ingestion must be enabled in production")
        if self.allow_synchronous_ingestion:
            errors.append("THISTINTI_ALLOW_SYNCHRONOUS_INGESTION must be false in production")
        if not self.require_malware_scanner:
            errors.append("Malware scanning must be mandatory in production")
        elif self.process_role in {"app", "worker"} and not self.malware_scanner_available:
            errors.append(f"Required malware scanner '{self.malware_scanner_command}' is unavailable")
        if self.self_hosted_reference:
            if not self.operator_accepts_self_hosting_responsibility:
                errors.append("Self-hosted operator responsibility acknowledgement is required")
            if not self.operator_accepts_no_support:
                errors.append("Self-hosted no-support acknowledgement is required")
            if len(self.deployment_id.strip()) < 8:
                errors.append("THISTINTI_DEPLOYMENT_ID must identify the operator-managed deployment")
            errors.extend(self.operator_acceptance_errors())
        return errors

    def validate_or_raise(self) -> None:
        errors = self.production_errors()
        if errors:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


settings = Settings()
settings.validate_or_raise()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.quarantine_dir.mkdir(parents=True, exist_ok=True)
settings.rejected_dir.mkdir(parents=True, exist_ok=True)
