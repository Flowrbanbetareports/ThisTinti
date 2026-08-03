from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_quality_assets_are_loaded_after_onboarding() -> None:
    loader = read(STATIC / "app.js")

    assert (STATIC / "product-polish.js").is_file()
    assert (STATIC / "product-polish.css").is_file()
    assert "'/product-polish.css'" in loader
    assert "'/product-polish.js'" in loader
    assert loader.index("'/onboarding.js'") < loader.index("'/product-polish.js'")
    assert loader.index("'/product-polish.js'") < loader.index("'/sidebar-scroll.js'")


def test_product_quality_layer_translates_internal_language_and_numbers() -> None:
    source = read(STATIC / "product-polish.js")

    for marker in (
        "credit_quantity: 'Quantità accreditata'",
        "unit_price: 'Prezzo unitario'",
        "return_without_credit: 'Reso senza nota di credito collegata'",
        "blocked: 'Controllo non superato'",
        "canonical_safe_baseline: 'Configurazione prudenziale'",
        "formatFlexibleNumber",
        "Indice tecnico ${score}/100 · non è una probabilità",
        "Priorità di controllo",
        "Qualità del motore",
        "Controlli proposti",
    ):
        assert marker in source


def test_product_quality_layer_keeps_advanced_claims_truthful() -> None:
    source = read(STATIC / "product-polish.js").lower()

    for marker in (
        "non è una probabilità",
        "nessuna regola viene presentata come verità automatica",
        "non rappresenta da sola una certificazione",
        "non autorizza pagamenti",
        "documenti originali",
    ):
        assert marker in source
    for forbidden in (
        "garantisce",
        "certificato automaticamente",
        "nessun errore possibile",
        "decisione certa",
    ):
        assert forbidden not in source


def test_product_quality_layer_is_local_and_does_not_send_messages() -> None:
    source = read(STATIC / "product-polish.js")

    for forbidden in (
        "http://",
        "https://",
        "XMLHttpRequest",
        "sendBeacon",
        "mailto:",
        "/api/email",
        "/api/messages",
    ):
        assert forbidden not in source
    assert "api('/api/audit')" in source


def test_product_quality_css_supports_focus_mobile_and_reduced_motion() -> None:
    css = read(STATIC / "product-polish.css")

    for marker in (
        ".supervision-note",
        ".product-technical-callout",
        ".activity-context",
        ".technical-score",
        ".risk-priority-high",
        ".audit-details",
        ":focus-visible",
        "@media (max-width: 780px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert marker in css


def test_real_browser_product_quality_check_is_in_repository() -> None:
    browser_check = ROOT / "scripts" / "check_product_polish_browser.py"
    assert browser_check.is_file()
    source = read(browser_check)
    assert "sync_playwright" in source
    assert "Priorità alta" in source
    assert "Quantità accreditata" in source
    assert "demoHidden" in source
