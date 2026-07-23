import json


def upload(client, auth, filename, payload):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={"file": (filename, json.dumps(payload).encode(), "application/json")},
    )


def test_proposal_invoice_payment_builds_proof_graph_and_balances_payment(client, auth):
    proposal = {
        "document_type": "proposal",
        "number": "PROP-100",
        "document_date": "2026-07-01",
        "supplier_name": "Sentinel Supplier",
        "lines": [{"sku": "A-1", "description": "Articolo A", "quantity": 10, "unit_price": 20}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-100",
        "document_date": "2026-07-10",
        "supplier_name": "Sentinel Supplier",
        "references": {"order_numbers": ["PROP-100"]},
        "lines": [{"sku": "A-1", "description": "Articolo A", "quantity": 10, "unit_price": 20}],
    }
    payment = {
        "document_type": "payment",
        "number": "PAY-100",
        "document_date": "2026-07-12",
        "supplier_name": "Sentinel Supplier",
        "references": {"invoice_numbers": ["INV-100"]},
        "lines": [{"description": "Pagamento fattura INV-100", "quantity": 1, "unit_price": 200}],
    }
    for filename, payload in (
        ("proposal.json", proposal),
        ("invoice.json", invoice),
        ("payment.json", payment),
    ):
        response = upload(client, auth, filename, payload)
        assert response.status_code == 201, response.text

    chains = client.get("/api/chains", headers=auth).json()
    assert len(chains) == 1
    chain = chains[0]
    assert set(chain["documents"]) >= {"proposal", "invoice", "payment"}

    response = client.get(f"/api/chains/{chain['id']}/intelligence", headers=auth)
    assert response.status_code == 200, response.text
    intelligence = response.json()
    roles = {node["role"] for node in intelligence["proof_graph"]["nodes"] if node["kind"] == "document"}
    assert {"proposal", "invoice", "payment"}.issubset(roles)
    assert intelligence["risk"]["payment_reconciliation"]["status"] == "balanced"
    explicit_edges = [edge for edge in intelligence["proof_graph"]["edges"] if edge["relation"] == "explicit_reference"]
    assert len(explicit_edges) >= 2
    assert intelligence["proof_graph"]["summary"]["explicit_reference_edges"] >= 2
    assert intelligence["risk"]["payment_reconciliation"]["delta"] == 0.0
    assert any(
        item["role"] == "delivery" and item["status"] == "missing_proof" for item in intelligence["expectations"]
    )
    assert intelligence["triangulation"]["status"] in {"needs_review", "blocked"}
    assert intelligence["process_conformance"]["baseline_sequence"][0] == "proposal"
    assert "order" not in intelligence["process_conformance"]["missing_between"]


def test_simulation_blocks_invoice_without_commercial_or_delivery_proof(client, auth):
    invoice = {
        "document_type": "invoice",
        "number": "INV-ORPHAN",
        "document_date": "2026-07-15",
        "supplier_name": "Orphan Supplier",
        "lines": [{"sku": "B-1", "quantity": 50, "unit_price": 12}],
    }
    assert upload(client, auth, "orphan.json", invoice).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    response = client.post(
        f"/api/chains/{chain_id}/simulate",
        headers=auth,
        json={"action": "approve_invoice"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["decision"] == "block"
    assert result["score"] >= 70
    assert result["amount_at_risk"] == 600.0
    assert any("Manca" in reason for reason in result["reasons"])
    assert result["safe_to_automate"] is False


def test_self_red_team_is_audited_and_does_not_mutate_documents(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-RED-1",
        "supplier_name": "Red Team Supplier",
        "lines": [{"sku": "R-1", "quantity": 5, "unit_price": 30}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-RED-1",
        "supplier_name": "Red Team Supplier",
        "references": {"order_numbers": ["PO-RED-1"]},
        "lines": [{"sku": "R-1", "quantity": 5, "unit_price": 30}],
    }
    assert upload(client, auth, "order.json", order).status_code == 201
    assert upload(client, auth, "invoice.json", invoice).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    before = len(client.get("/api/documents", headers=auth).json())

    response = client.post(f"/api/chains/{chain_id}/red-team", headers=auth)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == 7
    assert result["coverage"] > 0.5
    assert any(scenario["id"] == "cross_tenant_reference" and scenario["detected"] for scenario in result["scenarios"])
    assert len(client.get("/api/documents", headers=auth).json()) == before
    audit = client.get("/api/audit", headers=auth).json()
    assert any(event["action"] == "chain.red_team_run" for event in audit)


def test_intelligence_endpoint_is_tenant_isolated(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-INT-PRIVATE",
        "supplier_name": "Private Intelligence",
        "lines": [{"sku": "P-1", "quantity": 1, "unit_price": 1}],
    }
    assert upload(client, auth, "private-order.json", order).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    other = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Other Intelligence Tenant",
            "email": "other-intelligence@example.com",
            "password": "SecurePass456!",
        },
    )
    other_auth = {"Authorization": f"Bearer {other.json()['token']}"}
    assert client.get(f"/api/chains/{chain_id}/intelligence", headers=other_auth).status_code == 404


def test_payment_controls_detect_overpayment_and_duplicate_signature(client, auth):
    invoice = {
        "document_type": "invoice",
        "number": "INV-PAY-1",
        "supplier_name": "Payment Control Supplier",
        "lines": [{"sku": "PAY-A", "quantity": 1, "unit_price": 200}],
    }
    payment_one = {
        "document_type": "payment",
        "number": "POS-001",
        "supplier_name": "Payment Control Supplier",
        "references": {"invoice_numbers": ["INV-PAY-1"]},
        "lines": [{"description": "Pagamento INV-PAY-1", "quantity": 1, "unit_price": 200}],
    }
    payment_two = {
        "document_type": "payment",
        "number": "POS-002",
        "supplier_name": "Payment Control Supplier",
        "references": {"invoice_numbers": ["INV-PAY-1"]},
        "lines": [{"description": "Pagamento INV-PAY-1", "quantity": 1, "unit_price": 200}],
    }
    for filename, payload in (
        ("invoice-payment.json", invoice),
        ("payment-one.json", payment_one),
        ("payment-two.json", payment_two),
    ):
        response = upload(client, auth, filename, payload)
        assert response.status_code == 201, response.text
    case_types = {case["case_type"] for case in client.get("/api/cases", headers=auth).json()}
    assert "payment_over_invoice" in case_types
    assert "duplicate_payment" in case_types
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    intelligence = client.get(f"/api/chains/{chain_id}/intelligence", headers=auth).json()
    assert intelligence["risk"]["payment_reconciliation"]["duplicate_payment_groups"]


def test_payment_without_invoice_is_critical(client, auth):
    payment = {
        "document_type": "payment",
        "number": "POS-ORPHAN",
        "supplier_name": "Unlinked Payment Supplier",
        "lines": [{"description": "Pagamento non collegato", "quantity": 1, "unit_price": 350}],
    }
    assert upload(client, auth, "orphan-payment.json", payment).status_code == 201
    cases = client.get("/api/cases", headers=auth).json()
    case = next(item for item in cases if item["case_type"] == "payment_without_invoice")
    assert case["severity"] == "critical"
    assert case["amount_estimate"] == 350.0


def test_tenant_red_team_can_run_as_persistent_worker_job(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-JOB-RED",
        "supplier_name": "Scheduled Red Team Supplier",
        "lines": [{"sku": "J-1", "quantity": 3, "unit_price": 9}],
    }
    invoice = {
        "document_type": "invoice",
        "number": "INV-JOB-RED",
        "supplier_name": "Scheduled Red Team Supplier",
        "references": {"order_numbers": ["PO-JOB-RED"]},
        "lines": [{"sku": "J-1", "quantity": 3, "unit_price": 9}],
    }
    assert upload(client, auth, "job-order.json", order).status_code == 201
    assert upload(client, auth, "job-invoice.json", invoice).status_code == 201
    queued = client.post(
        "/api/jobs/red-team",
        headers={**auth, "Idempotency-Key": "tenant-red-team-1"},
    )
    assert queued.status_code == 202, queued.text

    from scripts.run_worker import run_once

    assert run_once("pytest-red-team-worker") is True
    completed = client.get(f"/api/jobs/{queued.json()['job']['id']}", headers=auth)
    assert completed.status_code == 200
    result = completed.json()
    assert result["status"] == "completed"
    assert result["result"]["chains"] == 1
    assert result["result"]["reports"][0]["total"] == 7


def test_sentinel_learns_supplier_timing_from_private_history(client, auth):
    historical = [
        ("H1", "2026-01-01", "2026-01-05"),
        ("H2", "2026-02-01", "2026-02-08"),
        ("H3", "2026-03-01", "2026-03-10"),
    ]
    for code, order_date, delivery_date in historical:
        order = {
            "document_type": "order",
            "number": f"PO-{code}",
            "document_date": order_date,
            "supplier_name": "Timing Supplier",
            "lines": [{"sku": f"SKU-{code}", "quantity": 1, "unit_price": 10, "unit_of_measure": "pz"}],
        }
        delivery = {
            "document_type": "delivery",
            "number": f"DDT-{code}",
            "document_date": delivery_date,
            "supplier_name": "Timing Supplier",
            "references": {"order_numbers": [f"PO-{code}"]},
            "lines": [{"sku": f"SKU-{code}", "quantity": 1, "unit_price": 10, "unit_of_measure": "pz"}],
        }
        assert upload(client, auth, f"order-{code}.json", order).status_code == 201
        assert upload(client, auth, f"delivery-{code}.json", delivery).status_code == 201

    current = {
        "document_type": "order",
        "number": "PO-H4",
        "document_date": "2026-07-01",
        "supplier_name": "Timing Supplier",
        "lines": [{"sku": "SKU-H4", "quantity": 1, "unit_price": 10, "unit_of_measure": "pz"}],
    }
    assert upload(client, auth, "order-H4.json", current).status_code == 201
    chains = client.get("/api/chains", headers=auth).json()
    current_chain = next(chain for chain in chains if chain["reference_key"] == "POH4")
    intelligence = client.get(f"/api/chains/{current_chain['id']}/intelligence", headers=auth).json()
    delivery = next(item for item in intelligence["expectations"] if item["role"] == "delivery")
    assert delivery["timing_source"] == "supplier_history_p80"
    assert delivery["sample_count"] >= 3
    assert delivery["due_date"] == "2026-07-10"


def test_process_conformance_uses_supplier_dominant_variant(client, auth):
    for index in range(1, 4):
        order_no = f"PO-V{index}"
        order = {
            "document_type": "order",
            "number": order_no,
            "document_date": f"2026-0{index}-01",
            "supplier_name": "Variant Supplier",
            "lines": [{"sku": f"V-{index}", "quantity": 1, "unit_price": 10}],
        }
        delivery = {
            "document_type": "delivery",
            "number": f"DDT-V{index}",
            "document_date": f"2026-0{index}-05",
            "supplier_name": "Variant Supplier",
            "references": {"order_numbers": [order_no]},
            "lines": [{"sku": f"V-{index}", "quantity": 1, "unit_price": 10}],
        }
        invoice = {
            "document_type": "invoice",
            "number": f"INV-V{index}",
            "document_date": f"2026-0{index}-08",
            "supplier_name": "Variant Supplier",
            "references": {"order_numbers": [order_no]},
            "lines": [{"sku": f"V-{index}", "quantity": 1, "unit_price": 10}],
        }
        for filename, payload in (
            (f"variant-order-{index}.json", order),
            (f"variant-delivery-{index}.json", delivery),
            (f"variant-invoice-{index}.json", invoice),
        ):
            assert upload(client, auth, filename, payload).status_code == 201

    current_order = {
        "document_type": "order",
        "number": "PO-V4",
        "document_date": "2026-07-01",
        "supplier_name": "Variant Supplier",
        "lines": [{"sku": "V-4", "quantity": 1, "unit_price": 10}],
    }
    current_invoice = {
        "document_type": "invoice",
        "number": "INV-V4",
        "document_date": "2026-07-03",
        "supplier_name": "Variant Supplier",
        "references": {"order_numbers": ["PO-V4"]},
        "lines": [{"sku": "V-4", "quantity": 1, "unit_price": 10}],
    }
    assert upload(client, auth, "variant-order-4.json", current_order).status_code == 201
    assert upload(client, auth, "variant-invoice-4.json", current_invoice).status_code == 201
    current_chain = next(
        chain for chain in client.get("/api/chains", headers=auth).json() if chain["reference_key"] == "POV4"
    )
    intelligence = client.get(f"/api/chains/{current_chain['id']}/intelligence", headers=auth).json()
    conformance = intelligence["process_conformance"]
    assert conformance["baseline_source"] == "supplier_dominant_variant"
    assert conformance["baseline_sequence"] == ["order", "delivery", "invoice"]
    assert conformance["status"] == "deviation"
    assert "delivery" in conformance["missing_between"]


def test_anonymous_pattern_pack_excludes_business_values(client, auth):
    sensitive_supplier = "SEGRETISSIMO FORNITORE ALFA"
    sensitive_number = "DOC-PRIVATE-938472"
    order = {
        "document_type": "order",
        "number": sensitive_number,
        "supplier_name": sensitive_supplier,
        "lines": [{"sku": "TOP-SECRET-SKU", "description": "Prodotto riservato", "quantity": 7, "unit_price": 123.45}],
    }
    assert upload(client, auth, "private-pattern.json", order).status_code == 201
    response = client.get("/api/intelligence/pattern-pack", headers=auth)
    assert response.status_code == 200, response.text
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert sensitive_supplier not in serialized
    assert sensitive_number not in serialized
    assert "TOP-SECRET-SKU" not in serialized
    assert "123.45" not in serialized
    assert payload["privacy"]["contains_documents"] is False
    assert payload["privacy"]["minimum_variant_support"] == 3
    assert "scenario_count" not in payload["validation"]
    assert "scenario_count_bucket" in payload["validation"]
    assert payload["pack_hash"]


def test_synthetic_validation_cannot_unlock_sentinel_automation(client, auth):
    invoice = {
        "document_type": "invoice",
        "number": "INV-CAL-SYNTH",
        "supplier_name": "Calibration Supplier",
        "lines": [{"sku": "CAL-1", "quantity": 1, "unit_price": 10}],
    }
    assert upload(client, auth, "calibration-invoice.json", invoice).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    dataset = client.post("/api/validation/load-default", headers=auth)
    assert dataset.status_code == 201
    run = client.post(f"/api/validation/datasets/{dataset.json()['id']}/run", headers=auth)
    assert run.status_code == 201
    assert run.json()["gate_passed"] is True

    intelligence = client.get(f"/api/chains/{chain_id}/intelligence", headers=auth).json()
    calibration = intelligence["risk"]["calibration"]
    assert calibration["raw_gate_passed"] is True
    assert calibration["gate_passed"] is False
    assert calibration["status"] == "synthetic_only"
    assert calibration["evidence_level"] == "synthetic"
    assert intelligence["risk"]["safe_to_automate"] is False


def test_synthetic_dataset_cannot_be_marked_automation_eligible(client, auth):
    response = client.post(
        "/api/validation/datasets",
        headers=auth,
        json={
            "name": "Unsafe synthetic gate",
            "version": "1",
            "evidence_level": "synthetic",
            "automation_eligible": True,
            "scenarios": [
                {
                    "id": "one",
                    "documents": [
                        {
                            "filename": "order.json",
                            "content": {
                                "document_type": "order",
                                "number": "O-1",
                                "supplier_name": "S",
                                "lines": [{"sku": "A", "quantity": 1, "unit_price": 1}],
                            },
                        }
                    ],
                    "expected": [],
                }
            ],
        },
    )
    assert response.status_code == 422


def test_real_pilot_automation_requires_separate_audited_approval(client, auth):
    scenarios = [
        {
            "id": f"clean-order-{index}",
            "documents": [
                {
                    "filename": f"order-{index}.json",
                    "content": {
                        "document_type": "order",
                        "number": f"PILOT-O-{index}",
                        "supplier_name": "Pilot Supplier",
                        "lines": [{"sku": f"A-{index}", "quantity": 1, "unit_price": 1}],
                    },
                }
            ],
            "expected": [],
        }
        for index in range(30)
    ]
    dataset_payload = {
        "name": "Anonymized pilot gate",
        "version": "1",
        "evidence_level": "anonymized_pilot",
        "automation_eligible": False,
        "evidence": {
            "authorization_reference": "TEST-PILOT-AUTH-001",
            "authorized_use_confirmed": True,
            "anonymization_confirmed": True,
            "anonymization_method": "Synthetic identifiers replace all business names and references in this test pilot.",
            "reviewer_refs": ["reviewer-a", "reviewer-b"],
            "ground_truth_method": "Two independent reviewers classify each scenario and reconcile disagreements.",
            "scope": "Thirty isolated order scenarios used to verify the audited automation gate in tests.",
            "prepared_at": "2025-01-01T00:00:00Z",
        },
        "scenarios": scenarios,
    }
    dataset = client.post("/api/validation/datasets", headers=auth, json=dataset_payload)
    assert dataset.status_code == 201, dataset.text
    dataset_id = dataset.json()["id"]

    before_gate = client.post(
        f"/api/validation/datasets/{dataset_id}/automation",
        headers=auth,
        json={"enabled": True, "note": "Approval requested before the measured gate"},
    )
    assert before_gate.status_code == 409

    run = client.post(f"/api/validation/datasets/{dataset_id}/run", headers=auth)
    assert run.status_code == 201
    assert run.json()["gate_passed"] is True
    approval = client.post(
        f"/api/validation/datasets/{dataset_id}/automation",
        headers=auth,
        json={"enabled": True, "note": "Pilot evidence reviewed and explicitly approved"},
    )
    assert approval.status_code == 200, approval.text
    assert approval.json()["automation_eligible"] is True
    runs = client.get(f"/api/validation/runs?dataset_id={dataset_id}", headers=auth).json()
    assert runs[0]["automation_approved"] is True
    approved_run_id = runs[0]["id"]

    operational_order = {
        "document_type": "order",
        "number": "APPROVED-PILOT-ORDER",
        "supplier_name": "Approved Pilot Supplier",
        "lines": [{"sku": "P-1", "quantity": 2, "unit_price": 10}],
    }
    assert upload(client, auth, "approved-pilot-order.json", operational_order).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]

    synthetic = client.post("/api/validation/load-default", headers=auth)
    assert synthetic.status_code == 201
    synthetic_run = client.post(
        f"/api/validation/datasets/{synthetic.json()['id']}/run",
        headers=auth,
    )
    assert synthetic_run.status_code == 201
    calibration = client.get(f"/api/chains/{chain_id}/intelligence", headers=auth).json()["risk"]["calibration"]
    assert calibration["status"] == "calibrated"
    assert calibration["run_id"] == approved_run_id
    assert calibration["gate_passed"] is True

    rerun = client.post(f"/api/validation/datasets/{dataset_id}/run", headers=auth)
    assert rerun.status_code == 201
    datasets = client.get("/api/validation/datasets", headers=auth).json()
    current = next(item for item in datasets if item["id"] == dataset_id)
    assert current["automation_eligible"] is False
    runs = client.get(f"/api/validation/runs?dataset_id={dataset_id}", headers=auth).json()
    assert runs[0]["automation_approved"] is False

    audit = client.get("/api/audit", headers=auth).json()
    assert any(event["action"] == "validation.automation_approved" for event in audit)


def test_database_rejects_synthetic_automation_eligibility(auth):
    import pytest
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models import Tenant, ValidationDataset

    with SessionLocal() as db:
        tenant_id = db.scalar(select(Tenant.id))
        dataset = ValidationDataset(
            tenant_id=tenant_id,
            name="Direct unsafe dataset",
            version="1",
            evidence_level="synthetic",
            automation_eligible=True,
            schema_json='{"name":"Direct unsafe dataset"}',
        )
        db.add(dataset)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_database_rejects_run_approval_without_audit_evidence(auth):
    import pytest
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models import Tenant, ValidationDataset, ValidationRun

    with SessionLocal() as db:
        tenant_id = db.scalar(select(Tenant.id))
        dataset = ValidationDataset(
            tenant_id=tenant_id,
            name="Pilot dataset",
            version="1",
            evidence_level="anonymized_pilot",
            automation_eligible=False,
            schema_json='{"name":"Pilot dataset"}',
        )
        db.add(dataset)
        db.flush()
        run = ValidationRun(
            tenant_id=tenant_id,
            dataset_id=dataset.id,
            status="completed",
            engine_version="3.2.0-alpha.1",
            scenario_count=30,
            gate_passed=True,
            automation_approved=True,
        )
        db.add(run)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_equal_unreferenced_payments_are_not_assumed_duplicates(client, auth):
    for index in (1, 2):
        payment = {
            "document_type": "payment",
            "number": f"UNLINKED-POS-{index}",
            "supplier_name": "Unreferenced Payments Supplier",
            "lines": [{"description": f"Pagamento generico {index}", "quantity": 1, "unit_price": 99}],
        }
        assert upload(client, auth, f"unreferenced-payment-{index}.json", payment).status_code == 201
    case_types = [case["case_type"] for case in client.get("/api/cases", headers=auth).json()]
    assert "payment_without_invoice" in case_types
    assert "duplicate_payment" not in case_types


def test_service_invoice_does_not_invent_missing_delivery(client, auth):
    invoice = {
        "document_type": "invoice",
        "number": "INV-SERVICE-1",
        "supplier_name": "Service Supplier",
        "lines": [
            {
                "description": "Servizio di consulenza mensile",
                "quantity": 1,
                "unit_price": 500,
            }
        ],
    }
    assert upload(client, auth, "service-invoice.json", invoice).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    intelligence = client.get(f"/api/chains/{chain_id}/intelligence", headers=auth).json()
    delivery_expectations = [item for item in intelligence["expectations"] if item["role"] == "delivery"]
    assert delivery_expectations == []
    assert any(item["role"] == "order" for item in intelligence["expectations"])


def test_simulation_blocks_action_when_target_document_does_not_exist(client, auth):
    order = {
        "document_type": "order",
        "number": "PO-NO-INVOICE",
        "supplier_name": "Missing Target Supplier",
        "lines": [{"sku": "X-1", "quantity": 2, "unit_price": 10}],
    }
    assert upload(client, auth, "order-without-invoice.json", order).status_code == 201
    chain_id = client.get("/api/chains", headers=auth).json()[0]["id"]
    response = client.post(
        f"/api/chains/{chain_id}/simulate",
        headers=auth,
        json={"action": "approve_invoice"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "block"
    assert result["safe_to_automate"] is False
    assert any("Nessun documento fattura" in reason for reason in result["reasons"])
