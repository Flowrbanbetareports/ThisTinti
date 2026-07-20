import io
import json
import zipfile
from pathlib import Path


def _upload_bytes(client, auth, name, content, mime="application/json", data=None):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (name, content, mime)},
        data=data or {},
    )


def test_security_headers_and_readiness(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    ready = client.get("/api/readiness")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True


def test_export_zip_contains_metadata(client, auth):
    sample = Path(__file__).parents[1] / "samples" / "order.json"
    with sample.open("rb") as handle:
        assert _upload_bytes(client, auth, "order.json", handle.read()).status_code == 201
    exported = client.get("/api/export", headers=auth)
    assert exported.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(exported.content))
    assert "export.json" in archive.namelist()
    payload = json.loads(archive.read("export.json"))
    assert payload["documents"][0]["document_type"] == "order"


def test_invalid_pdf_signature_rejected(client, auth):
    response = _upload_bytes(
        client,
        auth,
        "fake.pdf",
        b"not really a pdf",
        "application/pdf",
        {"document_type": "invoice", "supplier_name": "Supplier"},
    )
    assert response.status_code == 422
    assert "PDF valido" in response.json()["detail"]


def test_failed_csv_can_be_reprocessed(client, auth):
    csv_content = "Codice;Descrizione;Quantità;Prezzo unitario\nA-1;Giacca;10;20\n".encode()
    uploaded = _upload_bytes(client, auth, "order.csv", csv_content, "text/csv", {"supplier_name": "Supplier"})
    assert uploaded.status_code == 201
    doc = uploaded.json()["document"]
    assert doc["parse_status"] == "failed"
    reprocessed = client.post(
        f"/api/documents/{doc['id']}/reprocess",
        headers=auth,
        json={"document_type": "order", "supplier_name": "Supplier", "number": "PO-1", "document_date": "2026-07-01"},
    )
    assert reprocessed.status_code == 200, reprocessed.text
    assert reprocessed.json()["parse_status"] == "parsed"
    assert len(reprocessed.json()["lines"]) == 1


def test_reanalysis_is_idempotent(client, auth):
    sample_dir = Path(__file__).parents[1] / "samples"
    for name in ("order.json", "delivery.json", "invoice.json"):
        with (sample_dir / name).open("rb") as handle:
            assert _upload_bytes(client, auth, name, handle.read()).status_code == 201
    chain = client.get("/api/chains", headers=auth).json()[0]
    before = client.get("/api/cases", headers=auth).json()
    assert client.post(f"/api/chains/{chain['id']}/analyze", headers=auth).status_code == 200
    after = client.get("/api/cases", headers=auth).json()
    assert len(after) == len(before)
    assert {c["fingerprint"] if "fingerprint" in c else c["id"] for c in after} == {
        c["fingerprint"] if "fingerprint" in c else c["id"] for c in before
    }


def test_multiple_deliveries_are_aggregated(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-MULTI",
        "document_date": "2026-07-01",
        "supplier_name": "Multi Supplier",
        "lines": [{"sku": "A", "quantity": 100, "unit_price": 10}],
    }
    delivery_1 = {
        "document_type": "delivery",
        "number": "D1",
        "document_date": "2026-07-02",
        "supplier_name": "Multi Supplier",
        "references": {"order_numbers": ["PO-MULTI"]},
        "lines": [{"sku": "A", "quantity": 40, "unit_price": 10}],
    }
    delivery_2 = {
        "document_type": "delivery",
        "number": "D2",
        "document_date": "2026-07-03",
        "supplier_name": "Multi Supplier",
        "references": {"order_numbers": ["PO-MULTI"]},
        "lines": [{"sku": "A", "quantity": 60, "unit_price": 10}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "I1",
        "document_date": "2026-07-04",
        "supplier_name": "Multi Supplier",
        "references": {"order_numbers": ["PO-MULTI"]},
        "lines": [{"sku": "A", "quantity": 100, "unit_price": 10}],
    }
    for name, payload in (("o.json", order), ("d1.json", delivery_1), ("d2.json", delivery_2), ("i.json", invoice)):
        assert _upload_bytes(client, auth, name, json.dumps(payload).encode()).status_code == 201
    chains = client.get("/api/chains", headers=auth).json()
    assert len(chains) == 1
    assert len(chains[0]["documents"]["delivery"]) == 2
    cases = client.get("/api/cases", headers=auth).json()
    assert "invoiced_over_received" not in {c["case_type"] for c in cases if c["status"] != "superseded"}
