from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_experience_files_are_present_and_loaded_after_the_core():
    loader = read("app.js")
    assert (STATIC / "app-core.js").is_file()
    assert (STATIC / "onboarding.js").is_file()
    assert (STATIC / "onboarding.css").is_file()
    assert "'/app-core.js'" in loader
    assert "'/onboarding.js'" in loader
    assert "style.href = '/onboarding.css'" in loader
    assert loader.index("'/app-core.js'") < loader.index("'/onboarding.js'")


def test_primary_navigation_and_progressive_disclosure_are_defined():
    source = read("onboarding.js")
    for label in (
        "Inizio",
        "Documenti",
        "Da controllare",
        "Guida",
        "Strumenti avanzati",
        "Collegamenti",
        "Regole proposte",
        "Verifica delle regole",
        "Registro attività",
        "Utenti",
    ):
        assert label in source
    assert "advancedNavToggle" in source
    assert "advancedNavPanel" in source
    assert "aria-expanded" in source
    assert "aria-controls" in source


def test_first_use_path_has_preview_welcome_guide_and_start_checklist():
    source = read("onboarding.js")
    for marker in (
        "previewDialog",
        "welcomeDialog",
        "guideView",
        "gettingStartedPanel",
        "Prova con esempio",
        "Carica documenti",
        "Il risultato è una segnalazione, non una decisione",
    ):
        assert marker in source
    assert "showModal()" in source
    assert "aria-labelledby" in source


def test_experience_layer_does_not_bypass_authentication_or_upload_files():
    source = read("onboarding.js")
    forbidden = (
        "/api/auth/register",
        "/api/auth/login",
        "/api/documents/upload",
        "Authorization",
        "Bearer ",
        "document.cookie",
        "fetch(",
        "XMLHttpRequest",
    )
    for marker in forbidden:
        assert marker not in source
    assert "$('#demoButton')?.click()" in source
    assert "$('#openUploadButton')?.click()" in source


def test_language_remains_informative_and_non_authoritative():
    source = read("onboarding.js").lower()
    required = (
        "possibili differenze",
        "documenti originali",
        "non certifica",
        "non decide",
        "procedure dell’organizzazione",
    )
    for marker in required:
        assert marker in source
    forbidden = (
        "garantisce la conformità",
        "impedisce le frodi",
        "non sbaglia",
        "decisione corretta",
        "documento certamente errato",
    )
    for marker in forbidden:
        assert marker not in source


def test_experience_css_supports_small_screens_and_reduced_motion():
    css = read("onboarding.css")
    assert "@media (max-width: 700px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ".advanced-nav-panel" in css
    assert ".getting-started-panel" in css
    assert ".example-documents" in css
