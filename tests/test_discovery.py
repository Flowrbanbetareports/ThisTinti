import json
from pathlib import Path

SAMPLES = Path(__file__).parents[1] / "samples"


def upload_sample(client, auth, name):
    with (SAMPLES / name).open("rb") as handle:
        return client.post(
            "/api/documents/upload",
            headers=auth,
            files={"file": (name, handle, "application/json")},
        )


def upload_payload(client, auth, name, payload):
    content = json.dumps(payload).encode()
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (name, content, "application/json")},
    )


def test_discovery_runs_automatically_and_detects_activity(client, auth):
    for name in ("order.json", "delivery.json", "invoice.json"):
        response = upload_sample(client, auth, name)
        assert response.status_code == 201, response.text
    profile = client.get("/api/discovery/profile", headers=auth)
    assert profile.status_code == 200
    data = profile.json()
    assert data["profile"]["activity_type"] == "apparel"
    assert data["profile"]["document_count"] == 3
    assert data["summary"]["active_rules"] >= 5
    rules = client.get("/api/discovery/rules", headers=auth).json()
    assert any(rule["rule_code"] == "invoiced_over_received" and rule["status"] == "auto_active" for rule in rules)


def test_only_uncertain_rule_requires_confirmation(client, auth):
    for name in ("order.json", "delivery.json", "invoice.json", "return.json"):
        assert upload_sample(client, auth, name).status_code == 201
    rules = client.get("/api/discovery/rules", headers=auth).json()
    uncertain = next(rule for rule in rules if rule["rule_code"] == "credit_below_return")
    assert uncertain["status"] == "needs_confirmation"
    assert uncertain["requires_confirmation"] is True
    decision = client.post(
        f"/api/discovery/rules/{uncertain['id']}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "La nostra procedura richiede il confronto quantitativo."},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["rule"]["status"] == "confirmed"


def test_rejected_rule_is_not_applied(client, auth):
    for name in ("order.json", "delivery.json", "invoice.json", "return.json"):
        assert upload_sample(client, auth, name).status_code == 201
    rules = client.get("/api/discovery/rules", headers=auth).json()
    rule = next(rule for rule in rules if rule["rule_code"] == "return_without_credit")
    assert rule["status"] == "auto_active"
    before = client.get("/api/cases", headers=auth).json()
    assert any(case["case_type"] == "return_without_credit" and case["status"] != "superseded" for case in before)
    rejected = client.post(
        f"/api/discovery/rules/{rule['id']}/decision",
        headers=auth,
        json={"decision": "rejected", "note": "Gestito fuori sistema."},
    )
    assert rejected.status_code == 200
    after = client.get("/api/cases", headers=auth).json()
    assert any(case["case_type"] == "return_without_credit" and case["status"] == "superseded" for case in after)


def test_discovers_new_cross_document_field_rule(client, auth):
    common = {
        "supplier_name": "Device Supplier",
        "lines": [
            {
                "sku": "DEV-100",
                "description": "Industrial controller",
                "quantity": 1,
                "unit_price": 500,
                "serial_number": "SN-ORDER-001",
            }
        ],
    }
    order = {**common, "document_type": "order", "number": "PO-SERIAL-1"}
    invoice = {
        **common,
        "document_type": "invoice",
        "number": "INV-SERIAL-1",
        "references": {"order_number": "PO-SERIAL-1"},
        "lines": [{**common["lines"][0], "serial_number": "SN-INVOICE-999"}],
    }
    assert upload_payload(client, auth, "serial-order.json", order).status_code == 201
    assert upload_payload(client, auth, "serial-invoice.json", invoice).status_code == 201
    run = client.post(
        "/api/discovery/run",
        headers=auth,
        json={"minimum_documents": 2, "auto_activate_threshold": 0.92, "confirmation_threshold": 0.68},
    )
    assert run.status_code == 201, run.text
    rules = client.get("/api/discovery/rules", headers=auth).json()
    serial_rule = next(rule for rule in rules if rule["rule_code"] == "field_consistency:serial")
    assert serial_rule["status"] == "needs_confirmation"
    cases = client.get("/api/cases", headers=auth).json()
    assert not any(case["case_type"] == "field_consistency" for case in cases)
    decision = client.post(
        f"/api/discovery/rules/{serial_rule['id']}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Verified against the document schema"},
    )
    assert decision.status_code == 200, decision.text
    cases = client.get("/api/cases", headers=auth).json()
    assert any(case["case_type"] == "field_consistency" for case in cases)


def test_discovery_is_tenant_isolated(client, auth):
    for name in ("order.json", "delivery.json", "invoice.json"):
        assert upload_sample(client, auth, name).status_code == 201
    other = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Other Discovery Tenant",
            "email": "other-discovery@example.com",
            "password": "SecurePass456!",
        },
    )
    other_auth = {"Authorization": f"Bearer {other.json()['token']}"}
    profile = client.get("/api/discovery/profile", headers=other_auth).json()
    assert profile["profile"]["activity_type"] == "unknown"
    assert client.get("/api/discovery/rules", headers=other_auth).json() == []


def test_uncertain_activity_can_be_confirmed_or_corrected(client, auth):
    payloads = [
        {
            "document_type": role,
            "number": f"GEN-{index}",
            "supplier_name": "Generic Supplier",
            "references": {"order_number": "GEN-1"} if role != "order" else {},
            "lines": [{"sku": "X-1", "description": "Generic item", "quantity": 1, "unit_price": 10}],
        }
        for index, role in enumerate(("order", "delivery", "invoice"), start=1)
    ]
    for index, payload in enumerate(payloads, start=1):
        assert upload_payload(client, auth, f"generic-{index}.json", payload).status_code == 201
    profile = client.get("/api/discovery/profile", headers=auth).json()["profile"]
    assert profile["status"] in {"needs_confirmation", "ready"}
    corrected = client.post(
        "/api/discovery/profile/decision",
        headers=auth,
        json={
            "decision": "corrected",
            "activity_type": "specialized_distribution",
            "activity_label": "Distribuzione specializzata",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["profile"]["human_confirmed"] is True
    assert corrected.json()["profile"]["activity_label"] == "Distribuzione specializzata"
    rerun = client.post(
        "/api/discovery/run",
        headers=auth,
        json={"minimum_documents": 3, "auto_activate_threshold": 0.92, "confirmation_threshold": 0.68},
    )
    assert rerun.status_code == 201
    persisted = client.get("/api/discovery/profile", headers=auth).json()["profile"]
    assert persisted["activity_label"] == "Distribuzione specializzata"
