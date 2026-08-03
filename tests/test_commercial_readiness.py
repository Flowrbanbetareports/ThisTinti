from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.services.commercial import build_commercial_catalog

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
SITE = ROOT / "site"


def test_catalog_is_lightweight_and_does_not_activate_checkout_ads_or_telemetry():
    catalog = build_commercial_catalog()
    assert catalog["status"] == "preview_only"
    assert catalog["checkout_enabled"] is False
    assert catalog["advertising_enabled"] is False
    assert catalog["telemetry_enabled"] is False
    assert catalog["payments"]["status"] == "disabled"
    assert catalog["sponsorship"]["external_scripts"] is False
    boundary = catalog["payments"]["claim_boundary"].lower()
    assert "non possono impedire reclami legittimi" in boundary
    assert "diritti inderogabili" in boundary


def test_commercial_endpoints_expose_preview_and_downloadable_integration_pack(client, auth):
    catalog = client.get("/api/commercial/catalog", headers=auth)
    assert catalog.status_code == 200
    assert catalog.json()["checkout_enabled"] is False

    pack = client.get("/api/commercial/integration-pack", headers=auth)
    assert pack.status_code == 200
    assert pack.headers["content-type"].startswith("application/zip")
    assert "Integration-Pack" in pack.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(pack.content)) as archive:
        names = set(archive.namelist())
        assert "OPENAPI.json" in names
        assert "clients/python_client.py" in names
        assert "clients/javascript_client.js" in names
        assert "clients/CSharpExample.cs" in names
        assert "COMMERCIAL-PREVIEW.md" in names
        notice = archive.read("COMMERCIAL-PREVIEW.md").decode("utf-8")
        assert "Apache License 2.0" in notice
        assert "Nessun pagamento è attivo" in notice

    audit = client.get("/api/audit", headers=auth).json()
    assert any(item["action"] == "commercial.integration_pack_exported" for item in audit)


def test_commercial_page_is_admin_only_local_and_contains_no_ad_or_payment_provider():
    html = (STATIC / "commercial.html").read_text(encoding="utf-8")
    script = (STATIC / "commercial.js").read_text(encoding="utf-8")
    css = (STATIC / "commercial.css").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'data-admin-only href="/commercial.html"' in index
    assert "/api/auth/me" in script
    assert "/api/commercial/integration-pack" in html
    assert "Checkout disattivato" in html
    assert "Nessun annuncio" in html
    assert "flowrbanbetareports.github.io/ThisTinti/project.html" in html
    for source in (html, script):
        for forbidden in ("stripe.com", "paypal.com", "doubleclick", "googlesyndication", "sendBeacon"):
            assert forbidden not in source
    assert "@media (max-width: 680px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_public_project_dashboard_counts_github_assets_without_app_telemetry():
    html = (SITE / "project.html").read_text(encoding="utf-8")
    script = (SITE / "project.js").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")

    for marker in (
        "Download prodotto",
        "Installer Windows",
        "Self-hosted",
        "Workflow recenti",
        "non misurano utenti unici",
        "ThisTinti non invia telemetria",
    ):
        assert marker in html
    for marker in (
        "api.github.com/repos",
        "download_count",
        "actions/runs?per_page=20",
        "productDownloads",
        "allAssets",
    ):
        assert marker in script
    assert "node --check site/project.js" in workflow
    assert "'project.html', 'project.css', 'project.js'" in workflow
    for forbidden in ("document.cookie", "localStorage", "sendBeacon", "stripe.com", "paypal.com"):
        assert forbidden not in script
