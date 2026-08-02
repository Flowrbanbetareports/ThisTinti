from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from record_github_publication import published_asset_inventory  # noqa: E402


def test_publication_inventory_requires_every_manifested_asset(tmp_path: Path) -> None:
    (tmp_path / "required.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing verified assets"):
        published_asset_inventory([], tmp_path, {"required.json"})


def test_publication_inventory_accepts_only_extra_assets_backed_by_exact_artifact(tmp_path: Path) -> None:
    (tmp_path / "required.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "diagnostic-evidence.json").write_text("{}\n", encoding="utf-8")
    assets = [
        {"name": "required.json"},
        {"name": "diagnostic-evidence.json"},
    ]

    normalized, extras = published_asset_inventory(assets, tmp_path, {"required.json"})

    assert [item["name"] for item in normalized] == ["required.json", "diagnostic-evidence.json"]
    assert extras == {"diagnostic-evidence.json"}


def test_publication_inventory_rejects_unbacked_or_duplicate_assets(tmp_path: Path) -> None:
    (tmp_path / "required.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="absent from the verified artifact"):
        published_asset_inventory(
            [{"name": "required.json"}, {"name": "unknown.json"}],
            tmp_path,
            {"required.json"},
        )

    with pytest.raises(ValueError, match="duplicate or invalid"):
        published_asset_inventory(
            [{"name": "required.json"}, {"name": "required.json"}],
            tmp_path,
            {"required.json"},
        )
