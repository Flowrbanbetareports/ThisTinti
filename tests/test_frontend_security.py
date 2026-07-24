from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_frontend_does_not_store_session_tokens_in_web_storage():
    loader = read("app.js")
    core = read("app-core.js")
    experience = read("onboarding.js")

    assert "localStorage" not in loader
    assert "sessionStorage" not in loader
    assert "localStorage" not in core
    assert "sessionStorage" not in core

    # The experience layer may remember only non-sensitive presentation choices.
    assert "sessionStorage" not in experience
    assert "thistinti_experience_welcome_v1" in experience
    assert "thistinti_experience_advanced_v1" in experience
    for forbidden in ("token", "password", "email", "session", "csrf"):
        assert f"localStorage.setItem('{forbidden}" not in experience
        assert f'localStorage.setItem("{forbidden}' not in experience


def test_html_has_no_inline_style_attributes_for_strict_csp():
    html = read("index.html").lower()
    assert " style=" not in html


def test_frontend_core_uses_csrf_header_for_mutations():
    core = read("app-core.js")
    assert "X-CSRF-Token" in core
    assert "thistinti_csrf" in core
    assert "credentials: 'same-origin'" in core


def test_experience_layer_has_no_direct_network_or_authentication_logic():
    experience = read("onboarding.js")
    assert "fetch(" not in experience
    assert "XMLHttpRequest" not in experience
    assert "/api/auth" not in experience
    assert "Authorization" not in experience
    assert "document.cookie" not in experience
