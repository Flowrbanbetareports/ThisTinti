from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from procurement_pilot.common import (
    BACKLOG_FIELDS,
    RESULT_FIELDS,
    RESULT_SCHEMA,
    load_case_register,
    parse_bool,
    parse_non_negative_float,
    parse_non_negative_int,
    read_json,
    require_file,
    utc_now,
    wilson_interval,
    write_json,
)
from procurement_pilot.ground_truth import check_ready


def _summarize_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(item["true_positives"] for item in rows)
    fp = sum(item["false_positives"] for item in rows)
    fn = sum(item["false_negatives"] for item in rows)
    critical = sum(int(item["critical_miss"]) for item in rows)
    precision_denom = tp + fp
    recall_denom = tp + fn
    return {
        "case_count": len(rows),
        "raw_counts": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "critical_misses": critical,
            "precision_denominator": precision_denom,
            "recall_denominator": recall_denom,
        },
        "rates": {
            "precision": tp / precision_denom if precision_denom else None,
            "precision_95ci": wilson_interval(tp, precision_denom),
            "recall": tp / recall_denom if recall_denom else None,
            "recall_95ci": wilson_interval(tp, recall_denom),
        },
    }


def evaluate(workspace: Path) -> dict[str, Any]:
    readiness = check_ready(workspace)
    if not readiness["ready_for_blind_run"]:
        raise ValueError("blind run non valutabile: check-ready non superato")
    manifest = read_json(workspace / "pilot-manifest.json")
    results_path = require_file(workspace / "results" / "blind-results.csv", "blind-results.csv")
    with results_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != RESULT_FIELDS:
            raise ValueError("intestazioni blind-results.csv non valide")
        rows = list(reader)

    blind_ids = manifest["case_register"]["blind_case_ids"]
    if len(rows) != len(blind_ids):
        raise ValueError(f"servono {len(blind_ids)} risultati blind, trovati {len(rows)}")
    row_ids = [row["case_id"].strip() for row in rows]
    if set(row_ids) != set(blind_ids) or len(row_ids) != len(set(row_ids)):
        raise ValueError("case_id dei risultati non corrispondono esattamente al blind set")

    case_types = {row["case_id"].strip(): row["case_type"].strip() for row in load_case_register(workspace)}
    parsed_rows: list[dict[str, Any]] = []
    currencies: set[str] = set()
    potential_detected = potential_missed = confirmed_loss = avoided_loss = 0.0
    for row in rows:
        case_id = row["case_id"].strip()
        pdet = parse_non_negative_float(row["potential_exposure_detected"], "potential_exposure_detected")
        pmiss = parse_non_negative_float(row["potential_exposure_missed"], "potential_exposure_missed")
        closs = parse_non_negative_float(row["confirmed_loss"], "confirmed_loss")
        aloss = parse_non_negative_float(row["avoided_loss"], "avoided_loss")
        currency = row["currency"].strip().upper()
        if any(value > 0 for value in (pdet, pmiss, closs, aloss)) and not currency:
            raise ValueError(f"{case_id}: currency obbligatoria per valori economici")
        if currency:
            currencies.add(currency)
        parsed_rows.append(
            {
                "case_id": case_id,
                "case_type": case_types.get(case_id, ""),
                "true_positives": parse_non_negative_int(row["true_positives"], "true_positives"),
                "false_positives": parse_non_negative_int(row["false_positives"], "false_positives"),
                "false_negatives": parse_non_negative_int(row["false_negatives"], "false_negatives"),
                "critical_miss": parse_bool(row["critical_miss"], "critical_miss"),
                "potential_exposure_detected": pdet,
                "potential_exposure_missed": pmiss,
                "confirmed_loss": closs,
                "avoided_loss": aloss,
                "currency": currency or None,
            }
        )
        potential_detected += pdet
        potential_missed += pmiss
        confirmed_loss += closs
        avoided_loss += aloss

    overall = _summarize_counts(parsed_rows)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in parsed_rows:
        grouped[item["case_type"]].append(item)
    by_type = {case_type: _summarize_counts(group) for case_type, group in sorted(grouped.items())}

    if len(currencies) > 1:
        economics = {
            "currencies": sorted(currencies),
            "aggregation_allowed": False,
            "note": "Valori economici non aggregabili tra valute diverse.",
        }
    else:
        currency = next(iter(currencies), None)
        exposure_total = potential_detected + potential_missed
        economics = {
            "currency": currency,
            "aggregation_allowed": True,
            "potential_exposure_detected": round(potential_detected, 2),
            "potential_exposure_missed": round(potential_missed, 2),
            "confirmed_loss": round(confirmed_loss, 2),
            "avoided_loss": round(avoided_loss, 2),
            "exposure_weighted_recall": potential_detected / exposure_total if exposure_total else None,
            "note": "Gli importi del pilot non equivalgono automaticamente a perdite.",
        }

    gt_seal = read_json(workspace / "ground-truth.seal.json")
    critical_misses = overall["raw_counts"]["critical_misses"]
    threshold = manifest["preregistration"]["acceptance_thresholds"].get("critical_misses_max", 0)
    report = {
        "schema": RESULT_SCHEMA,
        "pilot_id": manifest["pilot_id"],
        "generated_at": utc_now(),
        "scope": {
            "domain": "procurement",
            "blind_case_count": len(parsed_rows),
            "wording": (
                f"Nel pilot cieco {manifest['pilot_id']}, su {len(parsed_rows)} pratiche "
                "appartenenti al perimetro preregistrato..."
            ),
        },
        "preregistration": manifest["preregistration"],
        "overall": overall,
        "results_by_case_type": by_type,
        "review": {
            "mode": gt_seal.get("review_mode"),
            "reviewer_disagreement_count": gt_seal.get("reviewer_disagreement_count"),
        },
        "economics": economics,
        "case_results": parsed_rows,
        "decision": (
            "blind_run_completed_with_critical_miss"
            if critical_misses > threshold
            else "blind_run_completed_no_critical_miss_observed"
        ),
        "claim_boundary": {
            "general_procurement_accuracy_claim_allowed": False,
            "production_certification": False,
            "blind_run_only": True,
            "small_sample_generalization_forbidden": True,
        },
        "backlog_rule": (
            "Gli errori scoperti in questo run non vengono corretti nel run stesso. "
            "Ogni modifica richiede un nuovo Manifest e un nuovo run."
        ),
    }
    write_json(workspace / "results" / "pilot-result.json", report)
    _write_markdown(workspace, report)
    _write_backlog(workspace, parsed_rows)
    return report


def _write_markdown(workspace: Path, report: dict[str, Any]) -> None:
    raw = report["overall"]["raw_counts"]
    rates = report["overall"]["rates"]
    precision = f"{rates['precision']:.3f}" if rates["precision"] is not None else "non calcolabile"
    recall = f"{rates['recall']:.3f}" if rates["recall"] is not None else "non calcolabile"
    lines = [
        f"# Risultato pilot {report['pilot_id']}",
        "",
        f"Blind set: **{report['scope']['blind_case_count']} pratiche**.",
        "",
        "## Conteggi grezzi",
        "",
        f"- True positive: {raw['true_positives']}",
        f"- False positive: {raw['false_positives']}",
        f"- False negative: {raw['false_negatives']}",
        f"- Critical miss: {raw['critical_misses']}",
        "",
        "## Percentuali e incertezza",
        "",
        f"- Precision: {precision}",
        f"- Recall: {recall}",
        f"- Precision 95% CI: {rates['precision_95ci']}",
        f"- Recall 95% CI: {rates['recall_95ci']}",
        "",
        "Le percentuali valgono esclusivamente per il perimetro e il run descritti dal Manifest.",
        "",
        "Questo rapporto non dimostra accuratezza generale sull'intero procurement e non costituisce certificazione.",
    ]
    (workspace / "results" / "pilot-result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_backlog(workspace: Path, rows: list[dict[str, Any]]) -> None:
    backlog: list[dict[str, str]] = []
    for item in rows:
        if item["false_negatives"]:
            backlog.append(
                {
                    "case_id": item["case_id"],
                    "error_type": "false_negative",
                    "severity": "critical" if item["critical_miss"] else "to_classify",
                    "description": f"{item['false_negatives']} false negative nel blind run",
                    "correction_target": "next_version_only",
                    "status": "open",
                }
            )
        if item["false_positives"]:
            backlog.append(
                {
                    "case_id": item["case_id"],
                    "error_type": "false_positive",
                    "severity": "to_classify",
                    "description": f"{item['false_positives']} false positive nel blind run",
                    "correction_target": "next_version_only",
                    "status": "open",
                }
            )
    with (workspace / "results" / "blind-backlog.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BACKLOG_FIELDS)
        writer.writeheader()
        writer.writerows(backlog)
