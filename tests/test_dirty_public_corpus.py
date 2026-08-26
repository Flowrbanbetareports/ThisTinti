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


def test_dirty_public_corpus_keeps_real_and_standard_sources_distinct() -> None:
    counts = Counter(item["category"] for item in load_manifest()["sources"])
    assert counts == {
        "real_public_transaction_pdf": 2,
        "external_standard_xml": 13,
        "external_edge_xml": 3,
        "external_negative_xml": 2,
        "real_public_nontransaction_pdf": 2,
    }


def test_github_sources_are_pinned_to_full_commits() -> None:
    full_sha = re.compile(r"^[0-9a-f]{40}$")
    for item in load_manifest()["sources"]:
        if "raw.githubusercontent.com" not in item["url"]:
            continue
        commit = item.get("source_commit")
        assert isinstance(commit, str) and full_sha.fullmatch(commit)
        assert f"/{commit}/" in item["url"]


def test_unfrozen_portland_sources_are_allowed_only_in_discovery_mode() -> None:
    manifest = load_manifest()
    portland = [item for item in manifest["sources"] if item["url"].startswith("https://www.portland.gov/")]
    assert len(portland) == 4
    if manifest["frozen"]:
        assert all(item.get("expected_sha256") for item in portland)
    else:
        assert any(not item.get("expected_sha256") for item in portland)


def test_expectations_do_not_claim_a_real_company_pilot() -> None:
    manifest = load_manifest()
    assert manifest["real_company_pilot"] is False
    for item in manifest["sources"]:
        assert item["expected"]["outcome"] in {"parse", "safe_rejection"}
        assert "accuracy" not in json.dumps(item, ensure_ascii=False).lower()
