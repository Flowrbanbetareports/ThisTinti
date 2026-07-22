from pathlib import Path

from app.version import RELEASE_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_current_brand_and_version_are_consistent() -> None:
    assert RELEASE_VERSION == "3.4.0-alpha.5"
    assert (ROOT / "run_thistinti.py").is_file()
    assert (ROOT / "installer/windows/ThisTinti.iss").is_file()
    assert (ROOT / "installer/windows/ThisTinti.spec").is_file()
    assert (ROOT / "installer/assets/thistinti.ico.b64").is_file()

    app_logo = (ROOT / "app/static/logo.svg").read_text(encoding="utf-8")
    site_logo = (ROOT / "site/logo.svg").read_text(encoding="utf-8")
    assert app_logo == site_logo
    assert "double-T monogram" in app_logo
    assert "#f0b64c" in app_logo
    assert "#55b4c3" in app_logo


def test_legacy_brand_is_absent_from_tracked_tree() -> None:
    old_tokens = ("This" + "Tinto", "THIS" + "TINTO", "this" + "tinto")
    excluded = {".git", ".pytest_cache", ".ruff_cache", "__pycache__"}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in excluded for part in relative.parts):
            continue
        assert not any(token in str(relative) for token in old_tokens), relative
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert not any(token in text for token in old_tokens), relative
