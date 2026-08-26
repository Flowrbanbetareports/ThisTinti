#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = ROOT / "samples" / "public_evidence_benchmark_30_sources.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the reproducible 30-case public-evidence benchmark.")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def line(sku: str, description: str, quantity: float, price: float, discount: float = 0) -> dict[str, Any]:
    return {
        "line_no": 1,
        "sku": sku,
        "description": description,
        "quantity": quantity,
        "unit_price": round(price, 2),
        "discount_rate": discount,
    }


def document(
    document_type: str,
    number: str,
    document_date: str,
    supplier: str,
    sku: str,
    description: str,
    quantity: float,
    price: float,
    discount: float = 0,
    references: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    return {
        "filename": f"{number}.json",
        "mime_type": "application/json",
        "content": {
            "document_type": document_type,
            "number": number,
            "document_date": document_date,
            "supplier_name": supplier,
            "references": references or {},
            "lines": [line(sku, description, quantity, price, discount)],
        },
    }


def public_order(record: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    ocid = record["ocid"]
    result = document(
        "order",
        ocid,
        record["start_date"],
        "Public source supplier not asserted",
        f"OCDS-{ocid.rsplit('-', 1)[-1]}",
        record["title"],
        1,
        record["amount"],
    )
    result["filename"] = f"{scenario_id}-order.json"
    result["content"].pop("supplier_name")
    result["content"]["_benchmark_provenance"] = {
        "source_kind": "public_ocds_normalization",
        "publisher": "City of Portland, Oregon",
        "source_id": record["source_id"],
        "ocid": ocid,
        "source_title": record["title"],
        "source_amount": record["amount"],
        "currency": record["currency"],
        "source_status": record["status"],
        "source_start_date": record["start_date"],
        "source_end_date": record["end_date"],
        "source_note": record["note"],
        "transformation": "minimal normalized representation; no downstream financial facts inferred",
    }
    return result


def expected(case_type: str, amount: float) -> list[dict[str, Any]]:
    return [
        {
            "case_type": case_type,
            "amount": round(amount, 2),
            "amount_tolerance": 0.0,
            "absolute_tolerance": 0.05,
        }
    ]


def build(sources: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    records = sources["records"]
    if len(records) != 10:
        raise ValueError("The v1 source manifest must freeze exactly 10 Portland records")

    scenarios: list[dict[str, Any]] = []
    truth: list[dict[str, Any]] = []

    for index, record in enumerate(records, start=1):
        scenario_id = f"public-baseline-{index:02d}"
        scenarios.append(
            {
                "id": scenario_id,
                "description": f"Faithful normalized Portland public record {record['ocid']}; no downstream document inferred.",
                "documents": [public_order(record, scenario_id)],
                "expected": [],
                "ignore_unexpected_types": [],
            }
        )
        truth.append(
            {
                "id": scenario_id,
                "category": "public_record_baseline",
                "source_id": record["source_id"],
                "ocid": record["ocid"],
                "expected": [],
                "mutation_type": None,
                "mutation": None,
                "ground_truth_rationale": "No anomaly is asserted; checks parsing and false-positive behavior on explicit public facts.",
            }
        )

    mutation_plan = [
        ("price_over_order", 500.0),
        ("price_over_order", 125.0),
        ("price_over_order", 1000.0),
        ("price_over_order", 250.0),
        ("invoiced_over_received", None),
        ("invoiced_over_received", None),
        ("discount_missing", None),
        ("discount_missing", None),
        ("unmatched_invoice_line", 333.0),
        ("unmatched_invoice_line", 777.0),
    ]

    for index, (record, plan) in enumerate(zip(records, mutation_plan, strict=True), start=1):
        mutation_type, value = plan
        scenario_id = f"public-mutation-{index:02d}"
        ocid = record["ocid"]
        amount = float(record["amount"])
        sku = f"OCDS-{ocid.rsplit('-', 1)[-1]}"
        supplier = f"Controlled derived supplier {index:02d}"
        order = public_order(record, scenario_id)
        order["content"]["supplier_name"] = supplier
        delivery = document(
            "delivery",
            f"DDT-PUB-{index:02d}",
            record["start_date"],
            supplier,
            sku,
            record["title"],
            1,
            amount,
            0,
            {"order_numbers": [ocid]},
        )
        invoice = document(
            "invoice",
            f"INV-PUB-{index:02d}",
            record["start_date"],
            supplier,
            sku,
            record["title"],
            1,
            amount,
            0,
            {"order_numbers": [ocid], "delivery_numbers": [f"DDT-PUB-{index:02d}"]},
        )
        mutation: dict[str, Any]
        frozen_expected: list[dict[str, Any]]
        if mutation_type == "price_over_order":
            invoice["content"]["lines"][0]["unit_price"] = round(amount + float(value), 2)
            frozen_expected = expected("price_over_order", float(value))
            mutation = {
                "field": "invoice.lines[0].unit_price",
                "baseline": amount,
                "mutated": round(amount + float(value), 2),
            }
        elif mutation_type == "invoiced_over_received":
            delivery["content"]["lines"][0]["quantity"] = 0.8
            frozen_expected = expected("invoiced_over_received", amount * 0.2)
            mutation = {"field": "delivery.lines[0].quantity", "baseline": 1, "mutated": 0.8}
        elif mutation_type == "discount_missing":
            order["content"]["lines"][0]["discount_rate"] = 5
            delivery["content"]["lines"][0]["discount_rate"] = 5
            invoice["content"]["lines"][0]["discount_rate"] = 0
            frozen_expected = expected("discount_missing", amount * 0.05)
            mutation = {"field": "invoice.lines[0].discount_rate", "baseline": 5, "mutated": 0}
        else:
            invoice["content"]["lines"].append(
                {
                    "line_no": 2,
                    "sku": f"EXTRA-PUB-{index:02d}",
                    "description": "Controlled unmatched charge",
                    "quantity": 1,
                    "unit_price": float(value),
                    "discount_rate": 0,
                }
            )
            frozen_expected = expected("unmatched_invoice_line", float(value))
            mutation = {
                "field": "invoice.lines",
                "baseline_count": 1,
                "mutated_count": 2,
                "added_line_amount": float(value),
            }
        invoice["content"]["_benchmark_provenance"] = {
            "derived_from_ocid": ocid,
            "mutation_type": mutation_type,
            "real_transaction_claim": False,
        }
        scenarios.append(
            {
                "id": scenario_id,
                "description": f"Derived from {ocid} with one frozen controlled mutation: {mutation_type}.",
                "documents": [order, delivery, invoice],
                "expected": [],
                "ignore_unexpected_types": [],
            }
        )
        truth.append(
            {
                "id": scenario_id,
                "category": "public_record_mutation",
                "source_id": record["source_id"],
                "ocid": ocid,
                "expected": frozen_expected,
                "mutation_type": mutation_type,
                "mutation": mutation,
                "ground_truth_rationale": "Expected result frozen from the single declared mutation before engine execution.",
            }
        )

    patterns = [
        ("clean", None),
        ("clean", None),
        ("price_over_order", 50.0),
        ("invoiced_over_received", None),
        ("discount_missing", None),
        ("unmatched_invoice_line", 75.0),
        ("return_without_credit", None),
        ("credit_below_return", None),
        ("price_over_order", 120.0),
        ("clean", None),
    ]
    base = date(2026, 8, 1)
    for index, (pattern, value) in enumerate(patterns, start=1):
        scenario_id = f"synthetic-full-chain-{index:02d}"
        supplier = f"Synthetic Professional Supplier {index:02d}"
        sku = f"SVC-{index:03d}"
        quantity = 10
        price = 100 + index * 5
        base_discount = 5 if pattern == "discount_missing" else 0
        order_no, delivery_no, invoice_no = f"PO-{index:03d}", f"DDT-{index:03d}", f"INV-{index:03d}"
        docs = [
            document(
                "proposal",
                f"PROP-{index:03d}",
                str(base),
                supplier,
                sku,
                "Professional benchmark service",
                quantity,
                price,
                base_discount,
            ),
            document(
                "order",
                order_no,
                str(base + timedelta(days=1)),
                supplier,
                sku,
                "Professional benchmark service",
                quantity,
                price,
                base_discount,
            ),
            document(
                "confirmation",
                f"CONF-{index:03d}",
                str(base + timedelta(days=2)),
                supplier,
                sku,
                "Professional benchmark service",
                quantity,
                price,
                base_discount,
                {"order_numbers": [order_no]},
            ),
        ]
        delivered = 8 if pattern == "invoiced_over_received" else quantity
        delivery = document(
            "delivery",
            delivery_no,
            str(base + timedelta(days=3)),
            supplier,
            sku,
            "Professional benchmark service",
            delivered,
            price,
            base_discount,
            {"order_numbers": [order_no]},
        )
        invoice_price = price + (float(value) / quantity if pattern == "price_over_order" else 0)
        invoice_discount = 0 if pattern == "discount_missing" else base_discount
        invoice = document(
            "invoice",
            invoice_no,
            str(base + timedelta(days=4)),
            supplier,
            sku,
            "Professional benchmark service",
            quantity,
            invoice_price,
            invoice_discount,
            {"order_numbers": [order_no], "delivery_numbers": [delivery_no]},
        )
        frozen_expected: list[dict[str, Any]] = []
        if pattern == "price_over_order":
            frozen_expected = expected("price_over_order", float(value))
        elif pattern == "invoiced_over_received":
            frozen_expected = expected("invoiced_over_received", 2 * price)
        elif pattern == "discount_missing":
            frozen_expected = expected("discount_missing", quantity * price * 0.05)
        elif pattern == "unmatched_invoice_line":
            invoice["content"]["lines"].append(
                {
                    "line_no": 2,
                    "sku": f"EXTRA-{index:03d}",
                    "description": "Synthetic handling fee",
                    "quantity": 1,
                    "unit_price": float(value),
                    "discount_rate": 0,
                }
            )
            frozen_expected = expected("unmatched_invoice_line", float(value))
        docs.extend([delivery, invoice])
        invoice_total = sum(
            float(item["quantity"]) * float(item["unit_price"]) * (1 - float(item.get("discount_rate", 0)) / 100)
            for item in invoice["content"]["lines"]
        )
        docs.append(
            document(
                "payment",
                f"PAY-{index:03d}",
                str(base + timedelta(days=6)),
                supplier,
                f"PAY-{index:03d}",
                f"Payment for {invoice_no}",
                1,
                invoice_total,
                0,
                {"invoice_numbers": [invoice_no]},
            )
        )
        if pattern == "return_without_credit":
            returned = 2
            docs.append(
                document(
                    "return",
                    f"RET-{index:03d}",
                    str(base + timedelta(days=7)),
                    supplier,
                    sku,
                    "Professional benchmark service",
                    returned,
                    price,
                    0,
                    {"order_numbers": [order_no], "invoice_numbers": [invoice_no]},
                )
            )
            frozen_expected = expected("return_without_credit", returned * price)
        elif pattern == "credit_below_return":
            returned, credited = 3, 1
            docs.append(
                document(
                    "return",
                    f"RET-{index:03d}",
                    str(base + timedelta(days=7)),
                    supplier,
                    sku,
                    "Professional benchmark service",
                    returned,
                    price,
                    0,
                    {"order_numbers": [order_no], "invoice_numbers": [invoice_no]},
                )
            )
            docs.append(
                document(
                    "credit_note",
                    f"CN-{index:03d}",
                    str(base + timedelta(days=9)),
                    supplier,
                    sku,
                    "Professional benchmark service",
                    credited,
                    price,
                    0,
                    {"order_numbers": [order_no], "invoice_numbers": [invoice_no]},
                )
            )
            frozen_expected = expected("credit_below_return", (returned - credited) * price)
        scenarios.append(
            {
                "id": scenario_id,
                "description": f"Professional synthetic end-to-end chain: {pattern}.",
                "documents": docs,
                "expected": [],
                "ignore_unexpected_types": [],
            }
        )
        truth.append(
            {
                "id": scenario_id,
                "category": "synthetic_full_chain",
                "source_id": None,
                "ocid": None,
                "expected": frozen_expected,
                "mutation_type": None if pattern == "clean" else pattern,
                "mutation": None,
                "ground_truth_rationale": "Fully synthetic professional chain with expected result frozen before execution.",
            }
        )

    dataset = {
        "name": "ThisTinti Public Evidence Benchmark 30",
        "version": "1.0.0",
        "description": "10 normalized public-source baselines, 10 controlled public-source mutations, 10 professional synthetic full chains. Ground truth is separate.",
        "evidence_level": "synthetic",
        "automation_eligible": False,
        "gate": {
            "min_precision": 0.95,
            "min_recall": 0.95,
            "min_f1": 0.95,
            "max_amount_mae": 0.05,
            "require_all_scenarios_pass": False,
        },
        "scenarios": scenarios,
    }
    ground_truth = {
        "schema": "thistinti.public-evidence-ground-truth.v1",
        "benchmark_name": dataset["name"],
        "benchmark_version": dataset["version"],
        "frozen_at": sources["frozen_at"],
        "evaluator_contract": "Engine ingestion receives benchmark documents only; expected findings are injected solely for post-output comparison.",
        "categories": {"public_record_baseline": 10, "public_record_mutation": 10, "synthetic_full_chain": 10},
        "source_manifest": "samples/public_evidence_benchmark_30_sources.json",
        "scenarios": truth,
    }
    return dataset, ground_truth


def main() -> int:
    args = parse_args()
    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    dataset, ground_truth = build(sources)
    write_json(args.dataset, dataset)
    write_json(args.ground_truth, ground_truth)
    print(f"Built {len(dataset['scenarios'])} scenarios and separated ground truth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
