#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Tenant, ValidationDataset  # noqa: E402
from app.schemas import ValidationDatasetPayload  # noqa: E402
from app.services.ingestion import ingest_path  # noqa: E402
from app.services.validation import run_validation_dataset  # noqa: E402
from app.version import RELEASE_VERSION  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the 30-scenario apparel pre-pilot and OCR scan diagnostic."
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--measurement-template", type=Path, required=True)
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _scan_text(index: int) -> list[str]:
    return [
        "FATTURA",
        f"Numero: INV-SCAN-{index:03d}",
        "Data: 01/08/2026",
        f"Fornitore: Fornitore Scan {index:02d}",
        f"Riferimento ordine: PO-SCAN-{index:03d}",
        f"Riferimento DDT: DDT-SCAN-{index:03d}",
        "",
        "SKU: MAGLIA-001",
        "Descrizione: Maglia cotone",
        "Quantita: 10",
        "Prezzo unitario: 12,50 EUR",
        "Sconto: 0%",
        "Totale: 125,00 EUR",
    ]


def create_scan_pdf(path: Path, index: int, variant: str) -> None:
    width, height = 1654, 2339
    background = 255 if variant != "low-contrast" else 238
    image = Image.new("L", (width, height), background)
    draw = ImageDraw.Draw(image)
    title_font = _font(54)
    body_font = _font(36)
    color = 15 if variant != "low-contrast" else 118
    y = 170
    for line_index, text in enumerate(_scan_text(index)):
        font = title_font if line_index == 0 else body_font
        draw.text((160, y), text, fill=color, font=font)
        y += 86 if line_index == 0 else 68

    if variant == "low-contrast":
        image = image.filter(ImageFilter.GaussianBlur(radius=0.8))
    elif variant == "rotated-noisy":
        noise = Image.effect_noise(image.size, 18).convert("L")
        image = Image.blend(image, noise, 0.08)
        image = image.rotate(
            1.7,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            fillcolor=255,
        )
        image = image.filter(ImageFilter.GaussianBlur(radius=0.35))

    image.convert("RGB").save(path, "PDF", resolution=200.0)


def _structured_document(
    document_type: str,
    number: str,
    supplier: str,
    order_number: str,
    delivery_number: str | None = None,
) -> dict[str, Any]:
    references: dict[str, list[str]] = {}
    if document_type != "order":
        references["order_numbers"] = [order_number]
    if delivery_number and document_type == "invoice":
        references["delivery_numbers"] = [delivery_number]
    return {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-01",
        "supplier_name": supplier,
        "references": references,
        "lines": [
            {
                "line_no": 1,
                "sku": "MAGLIA-001",
                "description": "Maglia cotone",
                "quantity": 10,
                "unit_price": 12.5,
                "discount_rate": 0,
            }
        ],
    }


def run_scan_diagnostic(db) -> list[dict[str, Any]]:
    variants = ("clear", "low-contrast", "rotated-noisy")
    results: list[dict[str, Any]] = []

    for index, variant in enumerate(variants, start=1):
        savepoint = db.begin_nested()
        storage_path: Path | None = None
        try:
            tenant = Tenant(
                name=f"Apparel scan diagnostic {index}",
                status="active",
            )
            db.add(tenant)
            db.flush()
            storage_path = settings.storage_dir / tenant.id
            supplier = f"Fornitore Scan {index:02d}"
            order_number = f"PO-SCAN-{index:03d}"
            delivery_number = f"DDT-SCAN-{index:03d}"

            with tempfile.TemporaryDirectory(prefix="thistinti-scan-pilot-") as directory:
                root = Path(directory)
                for sequence, (filename, content) in enumerate(
                    (
                        (
                            f"scan-{index}-order.json",
                            _structured_document(
                                "order",
                                order_number,
                                supplier,
                                order_number,
                            ),
                        ),
                        (
                            f"scan-{index}-delivery.json",
                            _structured_document(
                                "delivery",
                                delivery_number,
                                supplier,
                                order_number,
                            ),
                        ),
                    ),
                    start=1,
                ):
                    source = root / f"{sequence:03d}-{filename}"
                    source.write_text(
                        json.dumps(content, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    ingest_path(
                        db,
                        tenant.id,
                        source,
                        filename,
                        "application/json",
                        {},
                    )

                scan_path = root / f"scan-{index}-{variant}.pdf"
                create_scan_pdf(scan_path, index, variant)
                started = time.perf_counter()
                parsed, outcome = ingest_path(
                    db,
                    tenant.id,
                    scan_path,
                    scan_path.name,
                    "application/pdf",
                    {},
                )
                elapsed = time.perf_counter() - started
                results.append(
                    {
                        "id": f"scan-{index:02d}",
                        "variant": variant,
                        "outcome": outcome,
                        "parse_status": parsed.parse_status,
                        "parse_message": parsed.parse_message,
                        "document_type": parsed.document_type,
                        "number": parsed.number,
                        "confidence": float(parsed.confidence or 0),
                        "line_count": len(parsed.lines),
                        "elapsed_seconds": round(elapsed, 3),
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "id": f"scan-{index:02d}",
                    "variant": variant,
                    "outcome": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        finally:
            savepoint.rollback()
            if storage_path:
                shutil.rmtree(storage_path, ignore_errors=True)

    return results


def scenario_family(identifier: str) -> str:
    for prefix, family in (
        ("clean-", "catena coerente"),
        ("multi-clean-", "consegne e fatture multiple"),
        ("quantity-over-", "quantità fatturata oltre consegna"),
        ("price-over-", "prezzo superiore all'ordine"),
        ("discount-missing-", "sconto mancante"),
        ("unmatched-line-", "riga fattura non abbinata"),
        ("return-no-credit-", "reso senza nota di credito"),
        ("partial-credit-", "nota di credito parziale"),
        ("ambiguous-sku-", "codici articolo ambigui"),
    ):
        if identifier.startswith(prefix):
            return family
    return "altro"


def write_measurement_template(
    path: Path,
    payload: ValidationDatasetPayload,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "scenario_id",
        "famiglia",
        "revisore_1",
        "revisore_2",
        "tempo_manual_before_seconds",
        "tempo_with_thistinti_seconds",
        "anomalia_reale",
        "anomalia_segnalata",
        "falso_positivo",
        "falso_negativo",
        "giudizio_utilizzatore_1_5",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scenario in payload.scenarios:
            writer.writerow(
                {
                    "scenario_id": scenario.id,
                    "famiglia": scenario_family(scenario.id),
                }
            )


def build_markdown(report: dict[str, Any]) -> str:
    metrics = report["structured_benchmark"]["metrics"]
    scans = report["scan_diagnostic"]
    scan_rows = "\n".join(
        "| {id} | {variant} | {outcome} | {status} | {lines} | {seconds} |".format(
            id=item.get("id", "—"),
            variant=item.get("variant", "—"),
            outcome=item.get("outcome", "—"),
            status=item.get("parse_status", item.get("error", "—")),
            lines=item.get("line_count", "—"),
            seconds=item.get("elapsed_seconds", "—"),
        )
        for item in scans["items"]
    )
    return f"""# Pre-pilot ThisTinti — flusso abbigliamento

## Perimetro scelto

Un solo processo: **ordine → consegna → fattura → reso → nota di credito**.

Il benchmark usa esclusivamente dati sintetici. Non contiene documenti aziendali reali e
non autorizza dichiarazioni commerciali di accuratezza.

## Trenta pratiche strutturate

- pratiche: **{metrics["scenario_count"]}**
- documenti: **{metrics["document_count"]}**
- anomalie attese: **{metrics["expected_finding_count"]}**
- precisione: **{metrics["precision"]:.3f}**
- richiamo: **{metrics["recall"]:.3f}**
- F1: **{metrics["f1_score"]:.3f}**
- errore medio importi: **€ {metrics["amount_mae"]:.2f}**
- falsi positivi: **{metrics["false_positives"]}**
- falsi negativi: **{metrics["false_negatives"]}**
- gate tecnico superato: **{"SÌ" if metrics["gate_passed"] else "NO"}**
- tempo motore complessivo: **{metrics["elapsed_seconds"]:.3f} s**
- tempo medio per pratica: **{metrics["average_seconds_per_scenario"]:.3f} s**

## Scansioni sintetiche difficili

Questa prova separata usa tre PDF composti soltanto da immagini: una scansione pulita,
una a basso contrasto e una leggermente ruotata e rumorosa. È una diagnosi OCR, non una
misura di accuratezza su scansioni reali.

| Caso | Variante | Esito ingestione | Stato | Righe | Secondi |
|---|---|---|---|---:|---:|
{scan_rows}

## Misure non inventate

Il confronto **tempo umano prima/dopo** e il **giudizio degli utilizzatori** non sono
misurabili senza persone reali che eseguano lo stesso controllo. Per questo sono lasciati
esplicitamente aperti nel file CSV allegato invece di essere stimati o simulati.

## Conclusione corretta

Questo lavoro completa un **pre-pilot tecnico sintetico**. Il pilot reale richiede ancora:

1. almeno 30 pratiche aziendali autorizzate e, quando necessario, anonimizzate;
2. ground truth concordata da due revisori distinti;
3. tempi manuali e assistiti realmente cronometrati;
4. giudizio degli utilizzatori e registrazione dei falsi negativi conosciuti.
"""


def main() -> int:
    args = parse_args()
    raw = args.dataset.read_text(encoding="utf-8")
    payload = ValidationDatasetPayload.model_validate_json(raw)
    if len(payload.scenarios) != 30:
        raise ValueError("The apparel pre-pilot must contain exactly 30 scenarios")

    family_counts = Counter(scenario_family(item.id) for item in payload.scenarios)
    document_count = sum(len(item.documents) for item in payload.scenarios)
    expected_count = sum(len(item.expected) for item in payload.scenarios)

    db = SessionLocal()
    try:
        tenant = Tenant(name="ThisTinti apparel pre-pilot 30", status="active")
        db.add(tenant)
        db.flush()
        dataset = ValidationDataset(
            tenant_id=tenant.id,
            name=payload.name,
            version=payload.version,
            description=payload.description,
            schema_json=json.dumps(
                payload.model_dump(),
                ensure_ascii=False,
                default=str,
            ),
        )
        db.add(dataset)
        db.flush()

        started = time.perf_counter()
        run = run_validation_dataset(db, dataset, payload, actor_id=None)
        elapsed = time.perf_counter() - started
        db.commit()
        details = json.loads(run.details_json or "{}")

        scan_results = run_scan_diagnostic(db)
        scan_successes = sum(
            item.get("outcome") != "parse_failed"
            and item.get("parse_status") not in {"failed", "parse_failed"}
            and "error" not in item
            for item in scan_results
        )

        report = {
            "schema": "thistinti.apparel-pre-pilot.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "product": {
                "name": "ThisTinti",
                "engine_version": RELEASE_VERSION,
            },
            "classification": {
                "evidence_level": "synthetic",
                "real_pilot_completed": False,
                "commercial_accuracy_claim_allowed": False,
            },
            "process_scope": {
                "sector": "abbigliamento",
                "flow": [
                    "order",
                    "delivery",
                    "invoice",
                    "return",
                    "credit_note",
                ],
                "single_process_confirmed": True,
            },
            "structured_benchmark": {
                "dataset_name": payload.name,
                "dataset_version": payload.version,
                "families": dict(sorted(family_counts.items())),
                "metrics": {
                    "status": run.status,
                    "scenario_count": len(payload.scenarios),
                    "document_count": document_count,
                    "expected_finding_count": expected_count,
                    "true_positives": run.true_positives,
                    "false_positives": run.false_positives,
                    "false_negatives": run.false_negatives,
                    "precision": float(run.precision),
                    "recall": float(run.recall),
                    "f1_score": float(run.f1_score),
                    "amount_mae": float(run.amount_mae),
                    "gate_passed": bool(run.gate_passed),
                    "all_scenarios_pass": bool(
                        details.get("all_scenarios_pass")
                    ),
                    "elapsed_seconds": round(elapsed, 3),
                    "average_seconds_per_scenario": round(
                        elapsed / len(payload.scenarios),
                        3,
                    ),
                },
                "scenario_results": details.get("scenarios", []),
            },
            "scan_diagnostic": {
                "synthetic_image_only_pdfs": len(scan_results),
                "ingested_without_explicit_failure": scan_successes,
                "items": scan_results,
                "gating": False,
            },
            "human_measurement": {
                "manual_time_before_seconds": None,
                "assisted_time_after_seconds": None,
                "known_false_negatives_confirmed_by_reviewers": None,
                "user_judgment": None,
                "status": "requires_real_users_and_two_distinct_reviewers",
                "template": args.measurement_template.name,
            },
            "limitations": [
                "The 30 structured practices are synthetic.",
                "The OCR PDFs are generated images, not real supplier scans.",
                "Human before/after time has not been measured.",
                "No user judgment has been invented.",
                "A real pilot still requires authorized data and two reviewers.",
            ],
        }
        write_json(args.report, report)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(
            build_markdown(report),
            encoding="utf-8",
        )
        write_measurement_template(args.measurement_template, payload)
        print(json.dumps(report["structured_benchmark"]["metrics"], indent=2))
        return 0 if run.status == "completed" and run.gate_passed else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
