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
    assert "PARTIAL" in script
    assert "FAIL" in script


def test_diagnostics_do_not_claim_external_validation() -> None:
    html = (STATIC / "diagnostics.html").read_text(encoding="utf-8")

    assert "non può certificare" in html
    assert "tecnologie assistive" in html
    assert "firma Authenticode" in html
    assert "sicurezza indipendente" in html
