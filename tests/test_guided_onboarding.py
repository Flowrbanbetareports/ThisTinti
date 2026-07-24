from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_index_loads_guided_onboarding_assets() -> None:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/guide.css" />' in index
    assert '<script src="/guide.js" defer></script>' in index


def test_product_language_remains_neutral() -> None:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "ThisTinti non autorizza pagamenti" not in index
    assert "Le segnalazioni informano" in index
    assert "non sostituisce procedure, professionisti o decisioni" in index


def test_guide_contains_first_run_and_permanent_help() -> None:
    guide = (STATIC / "guide.js").read_text(encoding="utf-8")
    assert "guidedIntroDialog" in guide
    assert "guideView" in guide
    assert "Guida semplice" in guide
    assert "thistinti.guided-intro.v1" in guide
    assert "Carica esempio" in guide
    assert "Come si adatta alle aziende" in guide


def test_guide_assets_avoid_external_dependencies() -> None:
    guide_js = (STATIC / "guide.js").read_text(encoding="utf-8")
    guide_css = (STATIC / "guide.css").read_text(encoding="utf-8")
    assert "https://" not in guide_js
    assert "http://" not in guide_js
    assert "url(http" not in guide_css
