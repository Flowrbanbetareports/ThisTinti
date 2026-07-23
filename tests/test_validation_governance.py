import json


def _scenario(index: int) -> dict:
    return {
        "id": f"scenario-{index}",
        "documents": [
            {
                "filename": f"order-{index}.json",
                "content": {
                    "document_type": "order",
                    "number": f"ORDER-{index}",
                    "supplier_name": "Pilot Supplier",
                    "lines": [{"sku": f"SKU-{index}", "quantity": 1, "unit_price": 1}],
                },
            }
        ],
        "expected": [],
    }


def _evidence() -> dict:
    return {
        "authorization_reference": "PILOT-AUTH-001",
        "authorized_use_confirmed": True,
        "anonymization_confirmed": True,
        "anonymization_method": "Names, tax identifiers and document references were replaced before ingestion.",
        "reviewer_refs": ["reviewer-a", "reviewer-b"],
        "ground_truth_method": "Two independent reviewers classify each flow and reconcile every disagreement.",
        "scope": "Thirty anonymized order scenarios for the controlled document-validation pilot.",
        "prepared_at": "2025-01-01T00:00:00Z",
    }


def test_real_evidence_dataset_requires_governance_metadata(client, auth):
    payload = {
        "name": "Ungoverned pilot",
        "version": "1",
        "evidence_level": "anonymized_pilot",
        "scenarios": [_scenario(index) for index in range(30)],
    }
    response = client.post("/api/validation/datasets", headers=auth, json=payload)
    assert response.status_code == 422
    assert "authorization" in response.text.lower() or "metadata" in response.text.lower()


def test_real_evidence_dataset_requires_thirty_scenarios(client, auth):
    payload = {
        "name": "Undersized pilot",
        "version": "1",
        "evidence_level": "anonymized_pilot",
        "evidence": _evidence(),
        "scenarios": [_scenario(index) for index in range(29)],
    }
    response = client.post("/api/validation/datasets", headers=auth, json=payload)
    assert response.status_code == 422
    assert "30" in response.text


def test_real_evidence_dataset_requires_distinct_reviewers(client, auth):
    evidence = _evidence()
    evidence["reviewer_refs"] = ["Reviewer A", "reviewer a"]
    payload = {
        "name": "Single-reviewer pilot",
        "version": "1",
        "evidence_level": "anonymized_pilot",
        "evidence": evidence,
        "scenarios": [_scenario(index) for index in range(30)],
    }
    response = client.post("/api/validation/datasets", headers=auth, json=payload)
    assert response.status_code == 422
    assert "distinct" in response.text.lower()


def test_validation_report_is_downloadable_and_redacted(client, auth):
    loaded = client.post("/api/validation/load-default", headers=auth)
    assert loaded.status_code == 201, loaded.text
    run = client.post(f"/api/validation/datasets/{loaded.json()['id']}/run", headers=auth)
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]

    report = client.get(f"/api/validation/runs/{run_id}/report?format=json&redacted=true", headers=auth)
    assert report.status_code == 200, report.text
    assert report.headers["content-type"].startswith("application/json")
    assert "attachment" in report.headers["content-disposition"]
    payload = report.json()
    assert payload["schema"] == "thistinti.validation-report.v1"
    assert payload["redacted"] is True
    assert payload["run"]["id"] is None
    assert payload["run"]["gate_passed"] is True
    assert payload["quality_summary"]["failed_scenarios"] == 0
    assert all("id" not in scenario for scenario in payload["scenarios"])

    markdown = client.get(
        f"/api/validation/runs/{run_id}/report?format=markdown&redacted=true",
        headers=auth,
    )
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert "# Rapporto di validazione ThisTinti" in markdown.text
    assert "Gate: **PASS**" in markdown.text


def test_report_endpoint_is_tenant_isolated(client, auth):
    loaded = client.post("/api/validation/load-default", headers=auth).json()
    run = client.post(f"/api/validation/datasets/{loaded['id']}/run", headers=auth).json()
    other = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Other Report Tenant",
            "email": "other-report@example.com",
            "password": "SecurePass456!",
        },
    )
    other_auth = {"Authorization": f"Bearer {other.json()['token']}"}
    response = client.get(f"/api/validation/runs/{run['id']}/report", headers=other_auth)
    assert response.status_code == 404


def test_validation_report_contains_no_raw_dataset_documents(client, auth):
    loaded = client.post("/api/validation/load-default", headers=auth).json()
    run = client.post(f"/api/validation/datasets/{loaded['id']}/run", headers=auth).json()
    report = client.get(f"/api/validation/runs/{run['id']}/report", headers=auth)
    serialized = json.dumps(report.json(), ensure_ascii=False)
    assert "Fornitore Demo" not in serialized
    assert "GIACCA-145" not in serialized
    assert "INV-3921" not in serialized


def _token(client, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        headers={"X-Session-Mode": "token"},
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_redacted_report_hides_dataset_identity_and_sets_security_headers(client, auth):
    payload = {
        "name": "ACME confidential acquisition pilot",
        "version": "client-secret-v7",
        "scenarios": [_scenario(1)],
    }
    dataset = client.post("/api/validation/datasets", headers=auth, json=payload)
    assert dataset.status_code == 201, dataset.text
    run = client.post(f"/api/validation/datasets/{dataset.json()['id']}/run", headers=auth)
    assert run.status_code == 201, run.text

    report = client.get(f"/api/validation/runs/{run.json()['id']}/report?redacted=true", headers=auth)
    assert report.status_code == 200, report.text
    serialized = report.text
    assert "ACME confidential acquisition pilot" not in serialized
    assert "client-secret-v7" not in serialized
    assert "ACME" not in report.headers["content-disposition"]
    assert report.json()["dataset"]["name"] == "Dataset redatto"
    assert report.json()["dataset"]["version"] is None
    assert report.json()["dataset"]["reference"].startswith("dataset-")
    assert len(report.json()["source_fingerprints"]["dataset_sha256"]) == 64
    assert report.headers["cache-control"] == "no-store"
    assert report.headers["pragma"] == "no-cache"
    assert report.headers["x-content-type-options"] == "nosniff"

    audit = client.get("/api/audit", headers=auth)
    assert audit.status_code == 200
    exported = next(item for item in audit.json() if item["action"] == "validation.report_exported")
    assert exported["entity_id"] == run.json()["id"]
    assert exported["payload"]["redacted"] is True


def test_internal_validation_report_requires_admin(client, auth):
    loaded = client.post("/api/validation/load-default", headers=auth).json()
    run = client.post(f"/api/validation/datasets/{loaded['id']}/run", headers=auth).json()
    created = client.post(
        "/api/users",
        headers=auth,
        json={
            "email": "validation-reviewer@example.com",
            "password": "ReviewerPassword123!",
            "role": "reviewer",
        },
    )
    assert created.status_code == 201, created.text
    reviewer = _token(client, "validation-reviewer@example.com", "ReviewerPassword123!")

    assert client.get(f"/api/validation/runs/{run['id']}/report?redacted=true", headers=reviewer).status_code == 200
    blocked = client.get(f"/api/validation/runs/{run['id']}/report?redacted=false", headers=reviewer)
    assert blocked.status_code == 403


def test_real_evidence_requires_preparation_timestamp(client, auth):
    evidence = _evidence()
    evidence.pop("prepared_at")
    payload = {
        "name": "Missing evidence timestamp",
        "version": "1",
        "evidence_level": "anonymized_pilot",
        "evidence": evidence,
        "scenarios": [_scenario(index) for index in range(30)],
    }
    response = client.post("/api/validation/datasets", headers=auth, json=payload)
    assert response.status_code == 422
    assert "prepared_at" in response.text


def test_validation_scenario_ids_must_be_unique_case_insensitively(client, auth):
    first = _scenario(1)
    second = _scenario(2)
    second["id"] = " SCENARIO-1 "
    response = client.post(
        "/api/validation/datasets",
        headers=auth,
        json={"name": "Duplicate scenario ids", "version": "1", "scenarios": [first, second]},
    )
    assert response.status_code == 422
    assert "unique" in response.text.lower()
