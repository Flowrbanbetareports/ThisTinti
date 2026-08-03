from __future__ import annotations

from app.db import SessionLocal
from app.models import DocumentLine


def load_demo(client, auth):
    response = client.post("/api/demo/load", headers=auth)
    assert response.status_code == 200, response.text


def test_operational_overview_groups_cases_by_practice(client, auth):
    load_demo(client, auth)
    response = client.get("/api/operational/overview", headers=auth)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metrics"]["documents"] == 4
    assert payload["metrics"]["active_cases"] >= 5
    assert payload["metrics"]["practices_to_review"] == 1
    assert payload["next_case"]["chain_id"] == payload["practices"][0]["chain_id"]
    assert payload["practices"][0]["case_count"] >= 5
    assert payload["practices"][0]["amount_indicative"] > 0
    assert payload["system"]["status"] in {"operational", "attention"}


def test_case_history_and_operational_report_are_truthful(client, auth):
    load_demo(client, auth)
    case_item = client.get("/api/cases", headers=auth).json()[0]
    decision = client.post(
        f"/api/cases/{case_item['id']}/decision",
        headers=auth,
        json={"decision": "dismissed", "note": "Verificato sull'originale"},
    )
    assert decision.status_code == 200, decision.text
    history = client.get(f"/api/cases/{case_item['id']}/history", headers=auth)
    assert history.status_code == 200
    assert history.json()[-1]["decision"] == "dismissed"
    assert history.json()[-1]["note"] == "Verificato sull'originale"
    report = client.get("/api/operational/report", headers=auth)
    assert report.status_code == 200
    payload = report.json()
    assert payload["schema"] == "thistinti.operational-report.v1"
    assert payload["review"]["false_positive_proxy"] == 1
    assert payload["measurement_availability"]["manual_time_before"] is None
    assert payload["measurement_availability"]["known_false_negatives"] is None
    assert "non è una certificazione" in payload["claim_boundary"]


def test_human_line_correction_keeps_history_and_reanalyzes(client, auth):
    load_demo(client, auth)
    documents = client.get("/api/documents", headers=auth).json()
    invoice = next(item for item in documents if item["document_type"] == "invoice")
    detail = client.get(f"/api/documents/{invoice['id']}", headers=auth).json()
    line = next(item for item in detail["lines"] if item["sku"] == "GIACCA-145")
    response = client.patch(
        f"/api/document-lines/{line['id']}",
        headers=auth,
        json={
            "quantity": 114,
            "unit_price": 42,
            "discount_rate": 8,
            "reason": "Valori controllati sul documento originale",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected_chains"]
    updated = client.get(f"/api/documents/{invoice['id']}", headers=auth).json()
    corrected = next(item for item in updated["lines"] if item["id"] == line["id"])
    assert corrected["quantity"] == 114
    assert corrected["unit_price"] == 42
    assert corrected["discount_rate"] == 8
    assert corrected["numeric_provenance"]["quantity"] == "human_corrected"
    with SessionLocal() as db:
        stored = db.get(DocumentLine, line["id"])
        assert "Valori controllati sul documento originale" in stored.raw_json
        assert "correction_history" in stored.raw_json
    audit = client.get("/api/audit", headers=auth).json()
    assert any(event["action"] == "document_line.corrected" for event in audit)


def test_line_correction_requires_reason(client, auth):
    load_demo(client, auth)
    document = client.get("/api/documents", headers=auth).json()[0]
    line = client.get(f"/api/documents/{document['id']}", headers=auth).json()["lines"][0]
    invalid = client.patch(
        f"/api/document-lines/{line['id']}",
        headers=auth,
        json={"quantity": 2, "reason": "x"},
    )
    assert invalid.status_code == 422
