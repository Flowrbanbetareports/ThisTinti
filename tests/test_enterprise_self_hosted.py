from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

from scripts import enterprise_init, enterprise_preflight


ROOT = Path(__file__).resolve().parents[1]


def _prepared_deployment(tmp_path: Path) -> Path:
    deployment = tmp_path / "enterprise"
    deployment.mkdir()
    shutil.copy(ROOT / "deploy/enterprise/docker-compose.enterprise.yml", deployment / "docker-compose.enterprise.yml")
    shutil.copy(ROOT / "deploy/enterprise/Caddyfile", deployment / "Caddyfile")
    return deployment


def test_enterprise_init_and_preflight_are_fail_closed(monkeypatch, tmp_path: Path):
    deployment = _prepared_deployment(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "enterprise_init.py",
            "--directory",
            str(deployment),
            "--host",
            "thistinti.example.com",
            "--deployment-id",
            "selfhost-test-001",
            "--accept-operator-responsibility",
            "--accept-no-support",
        ],
    )
    assert enterprise_init.main() == 0
    monkeypatch.setattr(sys, "argv", ["enterprise_preflight.py", "--directory", str(deployment)])
    assert enterprise_preflight.main() == 0

    acceptance = json.loads((deployment / "operator-acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["transmitted_to_author"] is False
    assert acceptance["operator_accepts_self_hosting_responsibility"] is True
    assert (deployment / "secrets/database_app_url.txt").read_text().startswith("postgresql+psycopg://")


def test_enterprise_preflight_rejects_changed_legal_evidence(monkeypatch, tmp_path: Path):
    deployment = _prepared_deployment(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "enterprise_init.py",
            "--directory",
            str(deployment),
            "--host",
            "thistinti.example.com",
            "--accept-operator-responsibility",
            "--accept-no-support",
        ],
    )
    enterprise_init.main()
    path = deployment / "operator-acceptance.json"
    acceptance = json.loads(path.read_text(encoding="utf-8"))
    acceptance["legal_document_hashes"]["DISCLAIMER.md"] = "0" * 64
    path.write_text(json.dumps(acceptance), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["enterprise_preflight.py", "--directory", str(deployment)])
    assert enterprise_preflight.main() == 1


def test_enterprise_compose_exposes_only_proxy_and_uses_internal_backplane():
    compose = yaml.safe_load((ROOT / "deploy/enterprise/docker-compose.enterprise.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services["proxy"]["ports"]) == {"80:80", "443:443"}
    for name, service in services.items():
        if name != "proxy":
            assert "ports" not in service
    assert compose["networks"]["backplane"]["internal"] is True
    assert services["app"]["environment"]["THISTINTI_ALLOW_REGISTRATION"] == "false"
    assert services["app"]["environment"]["THISTINTI_REQUIRE_MALWARE_SCANNER"] == "true"
    assert services["worker"]["deploy"]["replicas"] == "${THISTINTI_WORKER_REPLICAS:-2}"


def test_build_and_release_exclude_operator_secrets():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "deploy/enterprise/secrets/" in dockerignore
    package_script = (ROOT / "scripts/package_release.py").read_text(encoding="utf-8")
    assert '"operator-acceptance.json"' in package_script
    assert '{"secrets", "backups", "logs"}' in package_script


def test_offline_admin_bootstrap_creates_only_first_user(monkeypatch):
    import io

    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import User
    from scripts import enterprise_create_admin

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "enterprise_create_admin.py",
            "--organization",
            "Bootstrap Company",
            "--email",
            "bootstrap@example.com",
            "--password-stdin",
        ],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("Secure-Bootstrap-Password-2026!\n"))
    assert enterprise_create_admin.main() == 0
    with SessionLocal() as db:
        assert int(db.scalar(select(func.count(User.id))) or 0) == 1

    monkeypatch.setattr(sys, "stdin", io.StringIO("Secure-Bootstrap-Password-2026!\n"))
    try:
        enterprise_create_admin.main()
    except RuntimeError as exc:
        assert "at least one user already exists" in str(exc)
    else:
        raise AssertionError("Second bootstrap must be refused")
