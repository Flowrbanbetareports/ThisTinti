from __future__ import annotations

from app.config import Settings


def _production_settings(**overrides):
    values = {
        "environment": "production",
        "process_role": "app",
        "database_url": "postgresql+psycopg://user:pass@example.test/db",
        "secret_key": "x" * 48,
        "auto_create_schema": False,
        "secure_cookies": True,
        "allow_registration": False,
        "async_ingestion_enabled": True,
        "allow_synchronous_ingestion": False,
        "database_rate_limiting": True,
        "require_malware_scanner": True,
        "malware_scanner_command": "definitely-missing-thistinti-scanner",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_refuses_optional_malware_scanning():
    settings = _production_settings(require_malware_scanner=False)
    assert "Malware scanning must be mandatory in production" in settings.production_errors()


def test_production_refuses_missing_required_scanner():
    settings = _production_settings()
    assert any("unavailable" in error for error in settings.production_errors())


def test_production_requires_shared_database_rate_limiting():
    settings = _production_settings(database_rate_limiting=False)
    assert "Database-backed rate limiting must be enabled in production" in settings.production_errors()


def test_production_migration_role_does_not_require_runtime_scanner_binary():
    settings = _production_settings(process_role="migrate")
    assert not any("unavailable" in error for error in settings.production_errors())


def _acceptance_file(tmp_path, deployment_id: str):
    import hashlib
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    names = ("LICENSE", "TERMS_OF_USE.md", "DISCLAIMER.md", "PRIVACY.md", "TRADEMARKS.md", "SUPPORT.md")
    payload = {
        "legal_notice_version": "2026-07-20-v2",
        "deployment_id": deployment_id,
        "operator_accepts_self_hosting_responsibility": True,
        "operator_accepts_no_guaranteed_support_or_sla": True,
        "legal_document_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names},
    }
    path = tmp_path / "operator-acceptance.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_self_hosted_production_requires_local_operator_evidence(tmp_path):
    settings = _production_settings(
        process_role="migrate",
        self_hosted_reference=True,
        operator_accepts_self_hosting_responsibility=True,
        operator_accepts_no_support=True,
        deployment_id="selfhost-test-001",
        operator_acceptance_file=None,
    )
    assert any("OPERATOR_ACCEPTANCE_FILE" in error for error in settings.production_errors())


def test_self_hosted_production_accepts_matching_local_evidence(tmp_path):
    deployment_id = "selfhost-test-001"
    settings = _production_settings(
        process_role="migrate",
        self_hosted_reference=True,
        operator_accepts_self_hosting_responsibility=True,
        operator_accepts_no_support=True,
        deployment_id=deployment_id,
        operator_acceptance_file=_acceptance_file(tmp_path, deployment_id),
    )
    assert settings.production_errors() == []
