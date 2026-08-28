from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from procurement_pilot.common import (
    BACKLOG_FIELDS,
    CASE_REGISTER_FIELDS,
    MAX_BLIND,
    MAX_CALIBRATION,
    MIN_BLIND,
    MIN_CALIBRATION,
    PLAN_SCHEMA,
    PRIVATE_INVENTORY_SCHEMA,
    RESULT_FIELDS,
    REVIEW_MODES,
    load_case_register,
    parse_bool,
    read_json,
    require_file,
    sha256_file,
    utc_now,
    write_json,
)


def default_preregistration() -> dict[str, Any]:
    return {
        "primary_metrics": [
            "raw_false_negatives",
            "critical_misses",
            "precision",
            "recall",
            "potential_exposure_missed",
        ],
        "secondary_metrics": [
            "raw_false_positives",
            "results_by_case_type",
            "exposure_weighted_recall_if_single_currency",
            "reviewer_disagreement_count_if_available",
        ],
        "critical_miss_definition": (
            "False negative che, nel perimetro preregistrato, può modificare in modo "
            "materiale la conclusione della pratica o lasciare non segnalata una possibile "
            "esposizione economica rilevante."
        ),
        "acceptance_thresholds": {
            "mode": "exploratory_no_general_accuracy_claim",
            "critical_misses_max": 0,
            "global_precision_threshold": None,
            "global_recall_threshold": None,
        },
        "inclusion_criteria": [
            "pratica procurement autorizzata nel perimetro concordato",
            "documenti originali o copie autorizzate disponibili per la ground truth",
            "case_id univoco e metadati di campionamento compilati",
        ],
        "exclusion_criteria": [
            "pratica non autorizzata",
            "duplicato o forte similarità con il gruppo opposto calibrazione/blind",
            "dati fuori dal perimetro preregistrato",
            "ground truth non completabile in modo affidabile",
        ],
        "sampling_strategy": (
            "Campionamento intenzionale orientato alla diversità. Separare calibrazione e "
            "blind set per similarity_group; privilegiare varietà di fornitore, template, "
            "qualità documentale, completezza e tipologia di caso."
        ),
        "abort_rules": [
            "modifica di qualsiasi artefatto congelato",
            "modifica del case-register dopo il freeze",
            "ground truth contaminata dall'output di ThisTinti",
            "documento non autorizzato o incidente privacy",
            "impossibilità di ricostruire la provenienza di una segnalazione critica",
            "richiesta di azioni esterne automatiche non autorizzate",
        ],
    }


def prepare_workspace(
    workspace: Path,
    pilot_id: str,
    organization_alias: str,
    calibration_count: int = 8,
    blind_count: int = 22,
    review_mode: str = "dual_independent",
) -> dict[str, Any]:
    if not MIN_CALIBRATION <= calibration_count <= MAX_CALIBRATION:
        raise ValueError(
            f"calibration_count deve essere tra {MIN_CALIBRATION} e {MAX_CALIBRATION}"
        )
    if not MIN_BLIND <= blind_count <= MAX_BLIND:
        raise ValueError(f"blind_count deve essere tra {MIN_BLIND} e {MAX_BLIND}")
    if review_mode not in REVIEW_MODES:
        raise ValueError(f"review_mode non valido: {review_mode}")

    workspace.mkdir(parents=True, exist_ok=True)
    for name in [
        "calibration",
        "blind",
        "ground-truth/reviewer-a",
        "ground-truth/reviewer-b",
        "ground-truth/adjudicated",
        "results",
        "private",
    ]:
        (workspace / name).mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, Any]] = []
    for phase, count, prefix in [
        ("calibration", calibration_count, "CAL"),
        ("blind", blind_count, "BLD"),
    ]:
        for index in range(1, count + 1):
            case_id = f"{prefix}-{index:03d}"
            (workspace / phase / case_id).mkdir(exist_ok=True)
            cases.append(
                {
                    "case_id": case_id,
                    "phase": phase,
                    "authorized": False,
                    "source_alias": "",
                    "template_family": "",
                    "similarity_group": "",
                    "case_type": "",
                    "notes": "",
                }
            )

    plan = {
        "schema": PLAN_SCHEMA,
        "pilot_id": pilot_id,
        "created_at": utc_now(),
        "domain": "procurement",
        "organization_alias": organization_alias,
        "status": "calibration_open",
        "methodology": {
            "calibration_case_count": calibration_count,
            "blind_case_count": blind_count,
            "freeze_required": True,
            "no_modifications_during_blind": True,
            "restart_run_on_frozen_change": True,
            "ground_truth_sealed_before_analysis": True,
            "counts_before_percentages": True,
            "similarity_leakage_forbidden": True,
        },
        "preregistration": default_preregistration(),
        "review": {
            "mode": review_mode,
            "reviewer_a": {"id": "REV-A", "role": "", "independent": True},
            "reviewer_b": {"id": "REV-B", "role": "", "independent": True},
            "single_reviewer_limitation_declared": (
                review_mode == "single_reviewer_with_declared_limitation"
            ),
        },
        "privacy": {
            "processing_location": "local_only",
            "document_hashes_private": True,
            "publish_document_hashes": False,
        },
        "cases": cases,
        "claim_boundary": {
            "general_procurement_accuracy_claim_allowed": False,
            "production_certification": False,
            "automatic_external_actions_allowed": False,
        },
    }
    write_json(workspace / "pilot-plan.json", plan)
    with (workspace / "case-register.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_REGISTER_FIELDS)
        writer.writeheader()
        writer.writerows(cases)
    for path, fields in [
        (workspace / "results" / "blind-results.csv", RESULT_FIELDS),
        (workspace / "results" / "blind-backlog.csv", BACKLOG_FIELDS),
    ]:
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fields).writeheader()
    (workspace / "README-FIRST.txt").write_text(
        "1) CAL-* serve alla calibrazione; BLD-* resta cieco.\n"
        "2) Compila case-register.csv e la preregistrazione.\n"
        "3) Esegui inventory-private, poi freeze.\n"
        "4) Crea e sigilla la ground truth prima dell'output di ThisTinti.\n"
        "5) Esegui check-ready prima del blind run.\n"
        "6) Durante il blind run ogni modifica richiede un nuovo Manifest.\n",
        encoding="utf-8",
    )
    return plan


def validate_case_register(plan: dict[str, Any], rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    expected = {item["case_id"]: item["phase"] for item in plan.get("cases", [])}
    seen: set[str] = set()
    groups: dict[str, set[str]] = {"calibration": set(), "blind": set()}
    for row in rows:
        case_id = (row.get("case_id") or "").strip()
        phase = (row.get("phase") or "").strip()
        if not case_id:
            errors.append("case-register: case_id mancante")
            continue
        if case_id in seen:
            errors.append(f"case-register: case_id duplicato {case_id}")
        seen.add(case_id)
        if expected.get(case_id) != phase:
            errors.append(f"{case_id}: fase non coerente con il piano")
        try:
            authorized = parse_bool(row.get("authorized", ""), "authorized")
        except ValueError:
            authorized = False
            errors.append(f"{case_id}: authorized non valido")
        if not authorized:
            errors.append(f"{case_id}: pratica non autorizzata")
        for field in ["source_alias", "template_family", "similarity_group", "case_type"]:
            if not (row.get(field) or "").strip():
                errors.append(f"{case_id}: {field} mancante")
        similarity_group = (row.get("similarity_group") or "").strip()
        if similarity_group and phase in groups:
            groups[phase].add(similarity_group)
    missing = sorted(set(expected) - seen)
    extras = sorted(seen - set(expected))
    if missing:
        errors.append(f"case-register: casi mancanti {missing}")
    if extras:
        errors.append(f"case-register: casi non previsti {extras}")
    overlap = sorted(groups["calibration"] & groups["blind"])
    if overlap:
        errors.append(
            "leakage: similarity_group presenti sia in calibrazione sia nel blind set: "
            + ", ".join(overlap)
        )
    return errors


def validate_preregistration(plan: dict[str, Any]) -> list[str]:
    prereg = plan.get("preregistration")
    if not isinstance(prereg, dict):
        return ["preregistration mancante"]
    required = [
        "primary_metrics",
        "secondary_metrics",
        "critical_miss_definition",
        "acceptance_thresholds",
        "inclusion_criteria",
        "exclusion_criteria",
        "sampling_strategy",
        "abort_rules",
    ]
    return [
        f"preregistration.{key} mancante o vuoto"
        for key in required
        if prereg.get(key) in (None, "", [], {})
    ]


def inventory_private_documents(workspace: Path) -> dict[str, Any]:
    plan = read_json(require_file(workspace / "pilot-plan.json", "pilot-plan.json"))
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("schema pilot-plan non valido")
    items: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for phase in ("calibration", "blind"):
        root = workspace / phase
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            case_id = path.relative_to(root).parts[0]
            counts[case_id] += 1
            items.append(
                {
                    "phase": phase,
                    "case_id": case_id,
                    "relative_path": path.relative_to(workspace).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    planned = {item["case_id"] for item in plan.get("cases", [])}
    missing = sorted(case_id for case_id in planned if counts.get(case_id, 0) == 0)
    payload = {
        "schema": PRIVATE_INVENTORY_SCHEMA,
        "pilot_id": plan["pilot_id"],
        "generated_at": utc_now(),
        "private": True,
        "must_not_be_published": True,
        "document_count": len(items),
        "case_document_counts": dict(sorted(counts.items())),
        "cases_without_documents": missing,
        "documents": items,
    }
    write_json(workspace / "private" / "document-inventory.json", payload)
    return payload
