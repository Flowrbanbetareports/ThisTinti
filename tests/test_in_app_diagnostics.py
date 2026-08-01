from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_diagnostics_assets_are_local_and_linked() -> None:
    html = (STATIC / "diagnostics.html").read_text(encoding="utf-8")
    css = (STATIC / "diagnostics.css").read_text(encoding="utf-8")
    script = (STATIC / "diagnostics.js").read_text(encoding="utf-8")
    link_script = (STATIC / "diagnostics-link.js").read_text(encoding="utf-8")
    app_loader = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'href="/diagnostics.css"' in html
    assert 'src="/diagnostics.js"' in html
    assert "https://" not in html
    assert "http://" not in html
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "window.location.assign('/diagnostics.html')" in link_script
    assert "loadScript('/diagnostics-link.js')" in app_loader
    assert "thistinti.local-diagnostics.v1" in script


def test_diagnostics_cover_core_supervised_workflow() -> None:
    script = (STATIC / "diagnostics.js").read_text(encoding="utf-8")

    for endpoint in (
        "/api/health",
        "/api/auth/me",
        "/openapi.json",
        "/api/dashboard",
        "/api/documents",
        "/api/chains",
        "/api/cases",
        "/api/jobs?limit=25",
        "/api/jobs/documents",
    ):
        assert endpoint in script

    assert "X-CSRF-Token" in script
    assert "credentials: 'same-origin'" in script
    assert "quantity: 'cinque'" in script
    assert "NON ESEGUITO" in script
    assert "PARZIALE" in script
    assert "FAIL" in script
    assert "SKIPPED" not in script
    assert "PARTIAL" not in script
    assert "healthVersion !== openapiVersion" in script
    assert "['admin', 'reviewer'].includes(session.role)" in script


def test_read_only_diagnostics_do_not_promote_the_active_check() -> None:
    script = (STATIC / "diagnostics.js").read_text(encoding="utf-8")
    documentation = (ROOT / "docs" / "IN_APP_DIAGNOSTICS.md").read_text(encoding="utf-8")

    assert "Il controllo sicuro non crea documenti" in script
    assert "['PARZIALE', 'NON ESEGUITO']" in script
    assert "NON ESEGUITO" in documentation
    assert "non sostituisce una prova umana" in documentation


def test_diagnostics_are_in_real_browser_ci_scope() -> None:
    workflow = (ROOT / ".github" / "workflows" / "simplified-experience.yml").read_text(encoding="utf-8")

    for path in (
        "app/static/diagnostics.html",
        "app/static/diagnostics.css",
        "app/static/diagnostics.js",
        "app/static/diagnostics-link.js",
        "scripts/check_in_app_diagnostics_browser.py",
    ):
        assert path in workflow
    assert "node --check app/static/diagnostics.js" in workflow
    assert "python scripts/check_in_app_diagnostics_browser.py" in workflow


def test_diagnostics_do_not_claim_external_validation() -> None:
    html = (STATIC / "diagnostics.html").read_text(encoding="utf-8")

    assert "non può certificare" in html
    assert "tecnologie assistive" in html
    assert "firma Authenticode" in html
    assert "sicurezza indipendente" in html
