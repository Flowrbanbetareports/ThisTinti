import json


def test_default_validation_dataset_passes_regression_gate(client, auth):
    loaded = client.post("/api/validation/load-default", headers=auth)
    assert loaded.status_code == 201, loaded.text
    dataset_id = loaded.json()["id"]

    run = client.post(f"/api/validation/datasets/{dataset_id}/run", headers=auth)
    assert run.status_code == 201, run.text
    payload = run.json()
    assert payload["status"] == "completed"
    assert payload["gate_passed"] is True
    assert payload["precision"] == 1.0
    assert payload["recall"] == 1.0
    assert payload["f1_score"] == 1.0
    assert payload["false_positives"] == 0
    assert payload["false_negatives"] == 0
    assert len(payload["details"]["scenarios"]) == 6
    assert all(scenario["passed"] for scenario in payload["details"]["scenarios"])


def test_validation_gate_fails_on_missing_expected_finding(client, auth):
    dataset = {
        "name": "Expected impossible finding",
        "version": "1",
        "gate": {
            "min_precision": 1,
            "min_recall": 1,
            "min_f1": 1,
            "max_amount_mae": 0,
            "require_all_scenarios_pass": True,
        },
        "scenarios": [
            {
                "id": "clean-but-expects-error",
                "documents": [
                    {
                        "filename": "order.json",
                        "content": {
                            "document_type": "order",
                            "number": "PO-V-1",
                            "supplier_name": "Validation Supplier",
                            "lines": [{"sku": "A", "quantity": 1, "unit_price": 10, "discount_rate": 0}],
                        },
                    }
                ],
                "expected": [{"case_type": "price_over_order", "amount": 10}],
            }
        ],
    }
    created = client.post("/api/validation/datasets", headers=auth, json=dataset)
    assert created.status_code == 201, created.text
    run = client.post(f"/api/validation/datasets/{created.json()['id']}/run", headers=auth)
    assert run.status_code == 201, run.text
    result = run.json()
    assert result["gate_passed"] is False
    assert result["false_negatives"] == 1
    assert result["recall"] == 0
    scenario = result["details"]["scenarios"][0]
    assert scenario["passed"] is False
    assert scenario["false_negatives"][0]["case_type"] == "price_over_order"


def test_validation_dataset_is_tenant_isolated(client, auth):
    loaded = client.post("/api/validation/load-default", headers=auth).json()
    other = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Other Validation Tenant",
            "email": "other-validation@example.com",
            "password": "SecurePass456!",
        },
    )
    other_auth = {"Authorization": f"Bearer {other.json()['token']}"}
    assert client.get(f"/api/validation/datasets/{loaded['id']}", headers=other_auth).status_code == 404
    assert client.post(f"/api/validation/datasets/{loaded['id']}/run", headers=other_auth).status_code == 404


def test_viewer_cannot_create_or_run_validation_dataset(client, auth):
    created = client.post(
        "/api/users",
        headers=auth,
        json={"email": "validation-viewer@example.com", "password": "SecurePass789!", "role": "viewer"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        headers={"X-Session-Mode": "token"},
        json={"email": "validation-viewer@example.com", "password": "SecurePass789!"},
    )
    viewer_auth = {"Authorization": f"Bearer {login.json()['token']}"}
    dataset = json.loads(open("samples/validation_core.json", encoding="utf-8").read())
    assert client.post("/api/validation/datasets", headers=viewer_auth, json=dataset).status_code == 403
    default_id = client.post("/api/validation/load-default", headers=auth).json()["id"]
    assert client.post(f"/api/validation/datasets/{default_id}/run", headers=viewer_auth).status_code == 403
    assert client.get("/api/validation/datasets", headers=viewer_auth).status_code == 200
