import json


def upload(client, auth, filename, payload):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )


def test_critical_cases_are_filtered_and_sorted_first(client, auth):
    mismatched_order = {
        "document_type": "order",
        "number": "ORDER-MISMATCH",
        "supplier_name": "Evidence Supplier",
        "lines": [{"sku": "A-1", "quantity": 2, "unit_price": 10, "discount_rate": 0, "line_total": 25}],
    }
    orphan_payment = {
        "document_type": "payment",
        "number": "PAY-CRITICAL",
        "supplier_name": "Evidence Supplier",
        "lines": [{"description": "Pagamento senza fattura", "quantity": 1, "unit_price": 100}],
    }
    assert upload(client, auth, "order-mismatch.json", mismatched_order).status_code == 201
    assert upload(client, auth, "orphan-payment.json", orphan_payment).status_code == 201

    cases = client.get("/api/cases", headers=auth).json()
    assert cases[0]["severity"] == "critical"
    assert any(item["severity"] == "medium" for item in cases)

    critical = client.get("/api/cases?severity=critical", headers=auth).json()
    assert critical
    assert all(item["severity"] == "critical" for item in critical)


def test_evidence_references_real_document_and_line(client, auth):
    payload = {
        "document_type": "order",
        "number": "ORDER-EVIDENCE",
        "supplier_name": "Line Evidence Supplier",
        "lines": [{"sku": "E-1", "description": "Riga da evidenziare", "quantity": 3, "unit_price": 10, "discount_rate": 0, "line_total": 40}],
    }
    response = upload(client, auth, "line-evidence.json", payload)
    assert response.status_code == 201, response.text

    case = next(item for item in client.get("/api/cases", headers=auth).json() if item["case_type"] == "line_total_mismatch")
    evidence = case["evidence"][0]
    assert evidence["document_id"]
    assert evidence["document_line_id"]

    document = client.get(f"/api/documents/{evidence['document_id']}", headers=auth).json()
    assert any(line["id"] == evidence["document_line_id"] for line in document["lines"])


def test_original_file_remains_available_after_archiving(client, auth):
    payload = {
        "document_type": "order",
        "number": "ORDER-ORIGINAL",
        "supplier_name": "Original Supplier",
        "lines": [{"sku": "O-1", "quantity": 1, "unit_price": 12, "line_total": 12}],
    }
    uploaded = upload(client, auth, "original.json", payload)
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["document"]["id"]

    original = client.get(f"/api/documents/{document_id}/file", headers=auth)
    assert original.status_code == 200
    assert original.headers["content-disposition"].startswith("attachment;")
    assert b"ORDER-ORIGINAL" in original.content

    assert client.post(f"/api/documents/{document_id}/archive", headers=auth).status_code == 200
    assert document_id not in {item["id"] for item in client.get("/api/documents", headers=auth).json()}
    archived_original = client.get(f"/api/documents/{document_id}/file", headers=auth)
    assert archived_original.status_code == 200
    assert archived_original.content == original.content
