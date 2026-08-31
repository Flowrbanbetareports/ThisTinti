from __future__ import annotations

from sqlalchemy import select

import app.api as api_module
from app.db import SessionLocal
from app.models import ChainDocument


def test_public_archive_reconciles_exactly_affected_chains(client, auth, monkeypatch):
    loaded = client.post("/api/demo/load", headers=auth)
    assert loaded.status_code == 200, loaded.text

    documents = client.get("/api/documents?limit=100", headers=auth).json()
    document_id = None
    expected_chain_ids: set[str] = set()
    with SessionLocal() as db:
        for document in documents:
            chain_ids = set(
                db.scalars(
                    select(ChainDocument.chain_id).where(
                        ChainDocument.tenant_id == document["tenant_id"]
                        if "tenant_id" in document
                        else ChainDocument.tenant_id.is_not(None),
                        ChainDocument.document_id == document["id"],
                    )
                )
            )
            if chain_ids:
                document_id = document["id"]
                expected_chain_ids = chain_ids
                break

    assert document_id is not None
    assert expected_chain_ids

    called: list[str] = []
    original_analyze_chain = api_module.analyze_chain

    def recording_analyze_chain(db, chain):
        called.append(chain.id)
        return original_analyze_chain(db, chain)

    monkeypatch.setattr(api_module, "analyze_chain", recording_analyze_chain)
    archived = client.post(f"/api/documents/{document_id}/archive", headers=auth)
    assert archived.status_code == 200, archived.text
    assert archived.json()["affected_chains"] == len(expected_chain_ids)
    assert set(called) == expected_chain_ids
