from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "samples" / "dirty_public_corpus_22.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_dirty_public_corpus_has_exact_scope_and_unique_ids() -> None:
    manifest = load_manifest()
    sources = manifest["sources"]
    assert manifest["schema"] == "thistinti.dirty-public-corpus.v1"
    assert manifest["real_company_pilot"] is False
    assert manifest["evidence_level"] == "public_external_raw"
    assert len(sources) == 22
    assert len({item["id"] for item in sources}) == 22
    assert len({item["url"] for item in sources}) == 22


def test_dirty_public_corpus_is_majority_real_public_financial_material() -> None:
    counts = Counter(item["category"] for item in load_manifest()["sources"])
    assert counts == {
        "real_public_financial_packet_pdf": 15,
        "external_standard_xml": 5,
        "external_edge_xml": 1,
        "external_conformance_negative_xml": 1,
    }


def test_all_external_files_are_pinned_to_full_github_commits() -> None:
    full_sha = re.compile(r"^[0-9a-f]{40}$")
    for item in load_manifest()["sources"]:
        assert "raw.githubusercontent.com" in item["url"]
        commit = item.get("source_commit")
        assert isinstance(commit, str) and full_sha.fullmatch(commit)
        assert f"/{commit}/" in item["url"]


def test_real_public_material_is_not_vendored_or_called_a_company_pilot() -> None:
    manifest = load_manifest()
    public_cases = [
        item
        for item in manifest["sources"]
        if item["category"] == "real_public_financial_packet_pdf"
    ]
    assert len(public_cases) == 15
    assert manifest["real_company_pilot"] is False
    assert all(item["publisher"] for item in public_cases)
    assert all(item.get("github_blob_sha") for item in public_cases)


def test_expectation_modes_preserve_characterization_boundary() -> None:
    manifest = load_manifest()
    outcomes = Counter(item["expected"]["outcome"] for item in manifest["sources"])
    assert outcomes["parse"] >= 9
    assert outcomes["characterize"] >= 10
    assert set(outcomes) <= {"parse", "safe_rejection", "characterize"}
    for item in manifest["sources"]:
        serialized = json.dumps(item, ensure_ascii=False).lower()
        assert "universal accuracy" not in serialized
        assert "real company pilot completed" not in serialized
