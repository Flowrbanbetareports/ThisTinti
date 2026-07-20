from __future__ import annotations

import json
from pathlib import Path

from app.legal import LEGAL_NOTICE_VERSION, has_current_acceptance, record_acceptance


def _legal_root(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in ("LICENSE", "TERMS_OF_USE.md", "DISCLAIMER.md", "PRIVACY.md", "TRADEMARKS.md"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    return tmp_path


def test_legal_acceptance_is_versioned_hashed_and_local(tmp_path: Path):
    resources = _legal_root(tmp_path / "resources")
    data_root = tmp_path / "data"
    path = record_acceptance(data_root, resources)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["legal_notice_version"] == LEGAL_NOTICE_VERSION
    assert payload["accepted_terms"] is True
    assert payload["accepted_specific_clauses"] is True
    assert payload["transmitted_to_author"] is False
    assert has_current_acceptance(data_root, resources) is True


def test_changed_legal_document_requires_new_acceptance(tmp_path: Path):
    resources = _legal_root(tmp_path / "resources")
    data_root = tmp_path / "data"
    record_acceptance(data_root, resources)
    (resources / "DISCLAIMER.md").write_text("changed", encoding="utf-8")
    assert has_current_acceptance(data_root, resources) is False


def test_distribution_contains_visible_legal_layers():
    root = Path(__file__).resolve().parents[1]
    for name in ("TERMS_OF_USE.md", "DISCLAIMER.md", "PRIVACY.md", "TRADEMARKS.md"):
        assert (root / name).exists()
    index = (root / "app/static/index.html").read_text(encoding="utf-8")
    assert "Output automatici da verificare" in index
    assert "acceptSpecificClauses" in index
    site = (root / "site/index.html").read_text(encoding="utf-8")
    assert "downloadRiskAcceptance" in site
    installer = (root / "installer/windows/ThisTinti.iss").read_text(encoding="utf-8")
    assert "1341 e 1342" in installer
    assert "SpecificApprovalCheck" in installer
