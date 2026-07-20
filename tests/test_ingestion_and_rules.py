from pathlib import Path

SAMPLES = Path(__file__).parents[1] / "samples"


def upload_json(client, auth, filename):
    path = SAMPLES / filename
    with path.open("rb") as handle:
        return client.post(
            "/api/documents/upload",
            headers=auth,
            files={"file": (filename, handle, "application/json")},
        )


def test_demo_chain_detects_expected_anomalies(client, auth):
    for name in ("order.json", "delivery.json", "invoice.json", "return.json"):
        response = upload_json(client, auth, name)
        assert response.status_code == 201, response.text
        assert response.json()["document"]["parse_status"] in {"parsed", "review_required"}

    chains = client.get("/api/chains", headers=auth).json()
    assert len(chains) == 1
    cases = client.get("/api/cases", headers=auth).json()
    case_types = {case["case_type"] for case in cases}
    assert "invoiced_over_received" in case_types
    assert "price_over_order" in case_types
    assert "discount_missing" in case_types
    assert "unmatched_invoice_line" in case_types
    assert "return_without_credit" in case_types


def test_credit_note_reduces_return_case(client, auth):
    for name in ("order.json", "delivery.json", "invoice.json", "return.json", "credit_note.json"):
        assert upload_json(client, auth, name).status_code == 201
    cases = client.get("/api/cases", headers=auth).json()
    types_by_status = {(c["case_type"], c["status"]) for c in cases}
    assert any(t == "credit_below_return" for t, _ in types_by_status)
    assert any(t == "return_without_credit" and s == "superseded" for t, s in types_by_status)


def test_duplicate_file_is_idempotent(client, auth):
    first = upload_json(client, auth, "order.json")
    second = upload_json(client, auth, "order.json")
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["outcome"] == "duplicate"
    docs = client.get("/api/documents", headers=auth).json()
    assert len(docs) == 1


def test_review_decision_is_audited(client, auth):
    for name in ("order.json", "delivery.json", "invoice.json"):
        upload_json(client, auth, name)
    case_id = client.get("/api/cases", headers=auth).json()[0]["id"]
    reviewed = client.post(
        f"/api/cases/{case_id}/decision", headers=auth, json={"decision": "confirmed", "note": "Checked"}
    )
    assert reviewed.status_code == 200
    audit = client.get("/api/audit", headers=auth).json()
    assert any(event["action"] == "case.reviewed" for event in audit)
