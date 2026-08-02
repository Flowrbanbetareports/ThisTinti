#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

SCHEMA = "thistinti.real-pilot-workspace.v1"
FLOW = ["order", "delivery", "invoice", "return", "credit_note"]
TEXT_SUFFIXES = {".csv", ".html", ".json", ".md", ".txt", ".xml"}
BINARY_DOCUMENT_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".xlsx"}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?39[ .-]?)?(?:0\d{2,3}|3\d{2})[ .-]?\d{5,8}(?!\w)")
VAT_RE = re.compile(r"\b(?:IT)?\d{11}\b", re.IGNORECASE)
TAX_CODE_RE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)
FORBIDDEN_NAME_PARTS = {"nome", "cognome", "email", "telefono", "iban", "partitaiva", "codicefiscale"}

MEASUREMENT_FIELDS = [
    "case_id",
    "reviewer_primary",
    "reviewer_secondary",
    "ground_truth_complete",
    "manual_seconds",
    "assisted_seconds",
    "actual_findings",
    "reported_findings",
    "false_positives",
    "false_negatives",
    "critical_miss",
    "user_score_1_to_5",
    "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: str, field: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes", "si", "sì"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{field}: valore booleano non valido")


def parse_non_negative_int(value: str, field: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field}: deve essere >= 0")
    return parsed


def parse_positive_float(value: str, field: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{field}: deve essere > 0")
    return parsed


def prepare_workspace(workspace: Path, pilot_id: str, organization_alias: str, case_count: int) -> dict[str, Any]:
    if case_count < 30:
        raise ValueError("Il pilot reale richiede almeno 30 pratiche")
    workspace.mkdir(parents=True, exist_ok=True)
    input_dir = workspace / "input"
    input_dir.mkdir(exist_ok=True)
    cases = []
    for index in range(1, case_count + 1):
        case_id = f"CASE-{index:03d}"
        (input_dir / case_id).mkdir(exist_ok=True)
        cases.append(
            {
                "case_id": case_id,
                "status": "awaiting_authorized_documents",
                "expected_document_types": FLOW,
                "document_count": 0,
            }
        )

    manifest = {
        "schema": SCHEMA,
        "pilot_id": pilot_id,
        "created_at": utc_now(),
        "sector": "abbigliamento",
        "process_flow": FLOW,
        "organization_alias": organization_alias,
        "evidence_level": "anonymized_pilot",
        "authorization": {
            "status": "pending",
            "authorized_by_role": "",
            "authorized_at": "",
            "processing_location": "local_only",
            "retention_end": "",
            "personal_data_expected": False,
            "notes": "",
        },
        "reviewers": [
            {"reviewer_id": "REV-A", "role": "", "independent": True},
            {"reviewer_id": "REV-B", "role": "", "independent": True},
        ],
        "cases": cases,
        "claim_boundary": {
            "safe_to_automate": False,
            "commercial_accuracy_claim_allowed": False,
            "production_claim_allowed": False,
        },
    }
    write_json(workspace / "pilot-manifest.json", manifest)

    with (workspace / "measurements.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_FIELDS)
        writer.writeheader()
        for item in cases:
            writer.writerow({"case_id": item["case_id"]})

    (workspace / "AUTHORIZATION.md").write_text(
        "# Autorizzazione pilot\n\n"
        "Stato: DA COMPILARE E FIRMARE DALL'ORGANIZZAZIONE AUTORIZZANTE.\n\n"
        f"Pilot: {pilot_id}\n\n"
        f"Organizzazione anonimizzata: {organization_alias}\n\n"
        "Perimetro: ordine, consegna, fattura, reso e nota di credito.\n\n"
        "I documenti possono essere utilizzati esclusivamente nel pilot locale e supervisionato descritto nel runbook. "
        "Nessuna azione esterna automatica è autorizzata.\n",
        encoding="utf-8",
    )
    return manifest


def scan_text(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [{"type": "encoding", "detail": "file testuale non UTF-8"}]
    findings: list[dict[str, Any]] = []
    patterns = {
        "email": EMAIL_RE,
        "iban": IBAN_RE,
        "phone": PHONE_RE,
        "vat_number": VAT_RE,
        "tax_code": TAX_CODE_RE,
    }
    for label, pattern in patterns.items():
        matches = pattern.findall(text)
        if matches:
            findings.append({"type": label, "count": len(matches)})
    return findings


def inspect_workspace(workspace: Path, output: Path | None = None) -> tuple[dict[str, Any], bool]:
    manifest_path = workspace / "pilot-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("pilot-manifest.json mancante")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema") != SCHEMA:
        errors.append("schema manifest non valido")
    if manifest.get("sector") != "abbigliamento":
        errors.append("settore non coerente con il pilot")
    if manifest.get("process_flow") != FLOW:
        errors.append("il pilot deve usare un solo flusso ordine-consegna-fattura-reso-nota di credito")
    if manifest.get("evidence_level") != "anonymized_pilot":
        errors.append("evidence_level deve essere anonymized_pilot")

    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) < 30:
        errors.append("servono almeno 30 pratiche")
    else:
        case_ids = [str(item.get("case_id", "")) for item in cases if isinstance(item, dict)]
        if len(case_ids) != len(set(case_ids)) or any(not value for value in case_ids):
            errors.append("case_id mancanti o duplicati")

    authorization = manifest.get("authorization") if isinstance(manifest.get("authorization"), dict) else {}
    if authorization.get("status") != "approved":
        warnings.append("autorizzazione non ancora approvata")
    if authorization.get("personal_data_expected") is not False:
        warnings.append("il pacchetto dichiara dati personali attesi")

    reviewers = manifest.get("reviewers") if isinstance(manifest.get("reviewers"), list) else []
    reviewer_ids = [str(item.get("reviewer_id", "")) for item in reviewers if isinstance(item, dict)]
    if len(set(reviewer_ids)) < 2:
        errors.append("servono due revisori distinti")

    pii_findings: list[dict[str, Any]] = []
    binary_manual_review: list[str] = []
    inventory: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace).as_posix()
        normalized_name = re.sub(r"[^a-z0-9]", "", path.name.casefold())
        forbidden_parts = sorted(part for part in FORBIDDEN_NAME_PARTS if part in normalized_name)
        if forbidden_parts:
            pii_findings.append({"path": relative, "type": "suspicious_filename", "matches": forbidden_parts})
        if path.suffix.casefold() in TEXT_SUFFIXES:
            for finding in scan_text(path):
                pii_findings.append({"path": relative, **finding})
        elif path.suffix.casefold() in BINARY_DOCUMENT_SUFFIXES:
            binary_manual_review.append(relative)
        inventory.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    if pii_findings:
        errors.append("possibili identificativi personali o aziendali rilevati")
    if binary_manual_review:
        warnings.append("i documenti binari richiedono conferma manuale di anonimizzazione")

    report = {
        "schema": "thistinti.real-pilot-inspection.v1",
        "generated_at": utc_now(),
        "workspace": str(workspace),
        "pilot_id": manifest.get("pilot_id"),
        "errors": errors,
        "warnings": warnings,
        "pii_findings": pii_findings,
        "binary_manual_review": binary_manual_review,
        "inventory": inventory,
        "structure_valid": not errors,
        "ready_for_execution": not errors and authorization.get("status") == "approved",
    }
    destination = output or workspace / "inspection.json"
    write_json(destination, report)
    return report, not errors


def load_measurements(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MEASUREMENT_FIELDS:
            raise ValueError("intestazioni measurements.csv non valide")
        return list(reader)


def summarize_workspace(workspace: Path, output: Path | None = None) -> tuple[dict[str, Any], bool]:
    measurement_path = workspace / "measurements.csv"
    if not measurement_path.is_file():
        raise ValueError("measurements.csv mancante")
    rows = load_measurements(measurement_path)
    if len(rows) < 30:
        raise ValueError("servono almeno 30 righe di misurazione")

    errors: list[str] = []
    manual_times: list[float] = []
    assisted_times: list[float] = []
    user_scores: list[int] = []
    false_positives = 0
    false_negatives = 0
    critical_misses = 0
    completed = 0
    reviewer_pairs: set[tuple[str, str]] = set()

    for index, row in enumerate(rows, start=2):
        case_id = row["case_id"].strip()
        if not case_id:
            errors.append(f"riga {index}: case_id mancante")
            continue
        try:
            primary = row["reviewer_primary"].strip()
            secondary = row["reviewer_secondary"].strip()
            if not primary or not secondary or primary == secondary:
                raise ValueError("servono due revisori distinti")
            reviewer_pairs.add((primary, secondary))
            if not parse_bool(row["ground_truth_complete"], "ground_truth_complete"):
                raise ValueError("ground truth non completata")
            manual = parse_positive_float(row["manual_seconds"], "manual_seconds")
            assisted = parse_positive_float(row["assisted_seconds"], "assisted_seconds")
            score = parse_non_negative_int(row["user_score_1_to_5"], "user_score_1_to_5")
            if score not in {1, 2, 3, 4, 5}:
                raise ValueError("user_score_1_to_5 deve essere tra 1 e 5")
            fp = parse_non_negative_int(row["false_positives"], "false_positives")
            fn = parse_non_negative_int(row["false_negatives"], "false_negatives")
            critical = parse_bool(row["critical_miss"], "critical_miss")
            parse_non_negative_int(row["actual_findings"], "actual_findings")
            parse_non_negative_int(row["reported_findings"], "reported_findings")
        except (TypeError, ValueError) as exc:
            errors.append(f"{case_id}: {exc}")
            continue
        manual_times.append(manual)
        assisted_times.append(assisted)
        user_scores.append(score)
        false_positives += fp
        false_negatives += fn
        critical_misses += int(critical)
        completed += 1

    total_manual = sum(manual_times)
    total_assisted = sum(assisted_times)
    savings = total_manual - total_assisted
    savings_percent = (savings / total_manual * 100) if total_manual else 0.0

    if errors or completed < 30:
        decision = "incompleto"
    elif critical_misses:
        decision = "non_idoneo"
    elif false_negatives:
        decision = "idoneo_solo_con_revisione_rafforzata"
    else:
        decision = "idoneo_con_revisione_umana"

    report = {
        "schema": "thistinti.real-pilot-result.v1",
        "generated_at": utc_now(),
        "case_count": len(rows),
        "completed_case_count": completed,
        "errors": errors,
        "metrics": {
            "manual_total_seconds": round(total_manual, 3),
            "assisted_total_seconds": round(total_assisted, 3),
            "time_saved_seconds": round(savings, 3),
            "time_saved_percent": round(savings_percent, 2),
            "manual_mean_seconds": round(mean(manual_times), 3) if manual_times else None,
            "assisted_mean_seconds": round(mean(assisted_times), 3) if assisted_times else None,
            "manual_median_seconds": round(median(manual_times), 3) if manual_times else None,
            "assisted_median_seconds": round(median(assisted_times), 3) if assisted_times else None,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "critical_misses": critical_misses,
            "average_user_score": round(mean(user_scores), 2) if user_scores else None,
            "reviewer_pair_count": len(reviewer_pairs),
        },
        "decision": decision,
        "claim_boundary": {
            "production_certification": False,
            "legal_or_accounting_certification": False,
            "automatic_external_actions_allowed": False,
        },
    }
    destination = output or workspace / "result.json"
    write_json(destination, report)
    markdown = workspace / "result.md"
    metrics = report["metrics"]
    markdown.write_text(
        "# Risultato pilot reale ThisTinti\n\n"
        f"- Pratiche complete: {completed}/{len(rows)}\n"
        f"- Tempo manuale totale: {metrics['manual_total_seconds']} s\n"
        f"- Tempo assistito totale: {metrics['assisted_total_seconds']} s\n"
        f"- Risparmio: {metrics['time_saved_percent']}%\n"
        f"- Falsi positivi: {false_positives}\n"
        f"- Falsi negativi: {false_negatives}\n"
        f"- Errori critici non rilevati: {critical_misses}\n"
        f"- Giudizio medio utilizzatori: {metrics['average_user_score']} / 5\n"
        f"- Decisione tecnica: **{decision}**\n\n"
        "La decisione resta limitata al processo e al campione autorizzato.\n",
        encoding="utf-8",
    )
    return report, not errors and completed >= 30


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepara, controlla e misura un pilot reale ThisTinti.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("workspace", type=Path)
    prepare.add_argument("--pilot-id", required=True)
    prepare.add_argument("--organization-alias", required=True)
    prepare.add_argument("--case-count", type=int, default=30)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("workspace", type=Path)
    inspect.add_argument("--output", type=Path)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("workspace", type=Path)
    summarize.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "prepare":
            prepare_workspace(args.workspace, args.pilot_id, args.organization_alias, args.case_count)
            return 0
        if args.command == "inspect":
            _, valid = inspect_workspace(args.workspace, args.output)
            return 0 if valid else 1
        if args.command == "summarize":
            _, complete = summarize_workspace(args.workspace, args.output)
            return 0 if complete else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Real pilot toolkit failed: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
