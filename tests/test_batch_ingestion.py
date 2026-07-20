import io
import json
import zipfile


def make_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


def test_batch_zip_ingests_supported_files_and_skips_unsafe_members(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-ZIP-1",
        "supplier_name": "ZIP Supplier",
        "lines": [{"sku": "ZIP-1", "quantity": 2, "unit_price": 10}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-ZIP-1",
        "supplier_name": "ZIP Supplier",
        "references": {"order_numbers": ["PO-ZIP-1"]},
        "lines": [{"sku": "ZIP-1", "quantity": 2, "unit_price": 10}],
    }
    archive = make_zip(
        [
            ("documents/order.json", json.dumps(order)),
            ("documents/invoice.json", json.dumps(invoice)),
            ("notes/readme.txt", "unsupported"),
            ("../escape.json", json.dumps(order)),
        ]
    )
    response = client.post(
        "/api/documents/batch",
        headers=auth,
        files={"file": ("batch.zip", archive, "application/zip")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["counts"]["ingested"] == 2
    assert payload["counts"]["skipped"] == 2
    assert payload["counts"]["failed"] == 0
    assert len(client.get("/api/documents", headers=auth).json()) == 2
    assert len(client.get("/api/chains", headers=auth).json()) == 1
    audit = client.get("/api/audit", headers=auth).json()
    assert any(event["action"] == "document.batch_uploaded" for event in audit)


def test_batch_rejects_non_zip_and_empty_zip(client, auth):
    wrong = client.post(
        "/api/documents/batch",
        headers=auth,
        files={"file": ("not-zip.json", b"{}", "application/json")},
    )
    assert wrong.status_code == 415
    empty = make_zip([])
    response = client.post(
        "/api/documents/batch",
        headers=auth,
        files={"file": ("empty.zip", empty, "application/zip")},
    )
    assert response.status_code == 422
