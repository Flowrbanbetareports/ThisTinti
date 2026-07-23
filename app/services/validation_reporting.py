from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ..models import ValidationDataset, ValidationRun
from ..version import RELEASE_VERSION

REPORT_SCHEMA = "thistinti.validation-report.v1"


def _fingerprint(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _details(run: ValidationRun) -> dict[str, Any]:
    try:
        value = json.loads(run.details_json or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _dataset_schema(dataset: ValidationDataset) -> dict[str, Any]:
    try:
        value = json.loads(dataset.schema_json or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _case_type_summary(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: Counter[str] = Counter()
    false_positives: Counter[str] = Counter()
    false_negatives: Counter[str] = Counter()
    for scenario in scenarios:
        for item in scenario.get("matches", []):
            case_type = str(item.get("case_type") or "unknown")
            matched[case_type] += 1
        for item in scenario.get("false_positives", []):
            case_type = str(item.get("case_type") or "unknown")
            false_positives[case_type] += 1
        for item in scenario.get("false_negatives", []):
            case_type = str(item.get("case_type") or "unknown")
            false_negatives[case_type] += 1
    keys = sorted(set(matched) | set(false_positives) | set(false_negatives))
    return [
        {
            "case_type": key,
            "true_positives": matched[key],
            "false_positives": false_positives[key],
            "false_negatives": false_negatives[key],
        }
        for key in keys
    ]


def build_validation_report(dataset: ValidationDataset, run: ValidationRun, *, redacted: bool = True) -> dict[str, Any]:
    details = _details(run)
    schema = _dataset_schema(dataset)
    scenarios = [item for item in details.get("scenarios", []) if isinstance(item, dict)]
    evidence = schema.get("evidence") if isinstance(schema.get("evidence"), dict) else None
    passed = sum(bool(item.get("passed")) for item in scenarios)
    parse_failures = sum(len(item.get("parse_failures", [])) for item in scenarios)

    evidence_summary: dict[str, Any] | None = None
    if evidence:
        reviewers = evidence.get("reviewer_refs") if isinstance(evidence.get("reviewer_refs"), list) else []
        evidence_summary = {
            "authorized_use_confirmed": bool(evidence.get("authorized_use_confirmed")),
            "anonymization_confirmed": bool(evidence.get("anonymization_confirmed")),
            "reviewer_count": len({str(item).strip().casefold() for item in reviewers if str(item).strip()}),
            "ground_truth_method_documented": bool(evidence.get("ground_truth_method")),
            "scope_documented": bool(evidence.get("scope")),
            "prepared_at": evidence.get("prepared_at"),
        }
        if not redacted:
            evidence_summary.update(
                {
                    "authorization_reference": evidence.get("authorization_reference"),
                    "anonymization_method": evidence.get("anonymization_method"),
                    "reviewer_refs": reviewers,
                    "ground_truth_method": evidence.get("ground_truth_method"),
                    "scope": evidence.get("scope"),
                    "notes": evidence.get("notes"),
                }
            )

    scenario_summary: list[dict[str, Any]] = []
    for index, item in enumerate(scenarios, start=1):
        summary = {
            "sequence": index,
            "passed": bool(item.get("passed")),
            "expected_count": int(item.get("expected_count") or 0),
            "found_count": int(item.get("found_count") or 0),
            "false_positive_count": len(item.get("false_positives", [])),
            "false_negative_count": len(item.get("false_negatives", [])),
            "parse_failure_count": len(item.get("parse_failures", [])),
            "error_present": bool(item.get("error")),
        }
        if not redacted:
            summary["id"] = item.get("id")
            summary["description"] = item.get("description")
            summary["error"] = item.get("error")
        scenario_summary.append(summary)

    dataset_fingerprint = _fingerprint(schema)
    run_fingerprint = _fingerprint(details)
    dataset_reference = f"dataset-{dataset_fingerprint[:12]}"

    return {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "redacted": redacted,
        "product": {"name": "ThisTinti", "version": RELEASE_VERSION},
        "source_fingerprints": {
            "dataset_sha256": dataset_fingerprint,
            "run_details_sha256": run_fingerprint,
        },
        "dataset": {
            "reference": dataset_reference,
            "name": "Dataset redatto" if redacted else dataset.name,
            "version": None if redacted else dataset.version,
            "evidence_level": dataset.evidence_level,
            "status": dataset.status,
            "scenario_count": run.scenario_count,
            "evidence": evidence_summary,
        },
        "run": {
            "id": None if redacted else run.id,
            "status": run.status,
            "engine_version": run.engine_version,
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "gate_passed": run.gate_passed,
            "automation_approved": run.automation_approved,
            "precision": run.precision,
            "recall": run.recall,
            "f1_score": run.f1_score,
            "amount_mae": float(run.amount_mae),
            "true_positives": run.true_positives,
            "false_positives": run.false_positives,
            "false_negatives": run.false_negatives,
        },
        "quality_summary": {
            "passed_scenarios": passed,
            "failed_scenarios": max(0, len(scenarios) - passed),
            "parse_failures": parse_failures,
            "all_scenarios_pass": bool(details.get("all_scenarios_pass")),
            "case_types": _case_type_summary(scenarios),
        },
        "gate": details.get("gate") if isinstance(details.get("gate"), dict) else {},
        "scenarios": scenario_summary,
        "limitations": [
            "Il rapporto misura esclusivamente il dataset e la versione del motore indicati.",
            "Le metriche sintetiche non dimostrano accuratezza su documenti aziendali reali.",
            "Gli output non autorizzano pagamenti, registrazioni contabili o comunicazioni verso terzi.",
            "La pubblicazione del rapporto richiede una revisione umana delle informazioni residue.",
        ],
    }


def render_validation_report_markdown(report: dict[str, Any]) -> str:
    dataset = report["dataset"]
    run = report["run"]
    quality = report["quality_summary"]
    evidence = dataset.get("evidence") or {}
    lines = [
        "# Rapporto di validazione ThisTinti",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Generato: {report['generated_at']}",
        f"- Versione prodotto: `{report['product']['version']}`",
        (
            f"- Dataset: **{dataset['name']}** · versione `{dataset['version']}`"
            if dataset.get("version")
            else f"- Dataset: **{dataset['name']}** · riferimento `{dataset['reference']}`"
        ),
        f"- Impronta dataset: `{report['source_fingerprints']['dataset_sha256']}`",
        f"- Evidenza: `{dataset['evidence_level']}`",
        f"- Scenari: **{dataset['scenario_count']}**",
        f"- Gate: **{'PASS' if run['gate_passed'] else 'STOP'}**",
        "",
        "## Metriche",
        "",
        f"- Precisione: {float(run['precision']):.2%}",
        f"- Recall: {float(run['recall']):.2%}",
        f"- F1: {float(run['f1_score']):.2%}",
        f"- Errore medio importi: {float(run['amount_mae']):.2f} EUR",
        f"- Veri positivi: {run['true_positives']}",
        f"- Falsi positivi: {run['false_positives']}",
        f"- Falsi negativi: {run['false_negatives']}",
        f"- Scenari superati: {quality['passed_scenarios']}",
        f"- Scenari falliti: {quality['failed_scenarios']}",
        f"- Fallimenti di parsing: {quality['parse_failures']}",
    ]
    if evidence:
        lines.extend(
            [
                "",
                "## Governance dell’evidenza",
                "",
                f"- Uso autorizzato confermato: {'sì' if evidence.get('authorized_use_confirmed') else 'no'}",
                f"- Anonimizzazione confermata: {'sì' if evidence.get('anonymization_confirmed') else 'no'}",
                f"- Revisori distinti: {evidence.get('reviewer_count', 0)}",
                f"- Ground truth documentata: {'sì' if evidence.get('ground_truth_method_documented') else 'no'}",
                f"- Perimetro documentato: {'sì' if evidence.get('scope_documented') else 'no'}",
            ]
        )
    lines.extend(["", "## Limiti", ""])
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    lines.append("")
    return "\n".join(lines)
