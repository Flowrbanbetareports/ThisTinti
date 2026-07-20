from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_does_not_store_session_tokens_in_web_storage():
    source = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "localStorage" not in source
    assert "sessionStorage" not in source


def test_html_has_no_inline_style_attributes_for_strict_csp():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8").lower()
    assert " style=" not in html


def test_frontend_uses_csrf_header_for_mutations():
    source = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "X-CSRF-Token" in source
    assert "thistinti_csrf" in source
