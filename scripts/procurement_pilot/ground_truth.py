from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from procurement_pilot.common import (
    FINANCIAL_STATUSES,
    GROUND_TRUTH_SCHEMA,
    IMPACT_TYPES,
    PRESENCE_STATES,
    REVIEW_SCHEMA,
    SEAL_SCHEMA,
    SUFFICIENCY_STATES,
    read_json,
    sha256_file,
    sha256_text,
    utc_now,
    write_json,
)
from procurement_pilot.freeze import verify_manifest_seal


def review_template(case_id: str, reviewer_id: str) -> dict[str, Any]:
    return {
        "schema": REVIEW_SCHEMA,
        "case_id": case_id,
        "reviewer_id": reviewer_id,
        "status": "pending",
        "created_without_thistinti_output": True,
        "expected": [],
        "observed": {"evidence": [], "facts": [], "interpretations": []},
        "judged": {"findings": []},
        "notes": "",
    }


def ground_truth_template(case_id: str, review_mode: str) -> dict[str, Any]:
    return {
        "schema": GROUND_TRUTH_SCHEMA,
        "case_id": case_id,
        "truth_version": "1",
        "created_without_thistinti_output": True,
        "review": {
            "mode": review_mode,
            "reviewer_a_completed": False,
            "reviewer_b_completed": False,
            "adjudication_status": "pending",
            "disagreement_count": 0,
            "single_reviewer_limitation": review_mode.startswith("single_reviewer"),
        },
        "expected": [],
        "observed": {"evidence": [], "facts": [], "interpretations": []},
        "judged": {"findings": []},
        "controlled_vocabularies": {
            "presence_states": sorted(PRESENCE_STATES),
            "evidentiary_sufficiency_states": sorted(SUFFICIENCY_STATES),
            "impact_types": sorted(IMPACT_TYPES),
            "financial_statuses": sorted(FINANCIAL_STATUSES),
        },
    }


def create_ground_truth_templates(workspace: Path) -> dict[str, Any]:
    manifest, errors = verify_manifest_seal(workspace)
    if errors:
        raise ValueError("manifest non integro:\n- " + "\n- ".join(errors))
    review_mode = manifest["review"]["mode"]
    created: list[str] = []
    for case_id in manifest["case_register"]["blind_case_ids"]:
        a_path = workspace / "ground-truth" / "reviewer-a" / f"{case_id}.json"
        if not a_path.exists():
            write_json(a_path, review_template(case_id, "REV-A"))
        if review_mode == "dual_independent":
            b_path = workspace / "ground-truth" / "reviewer-b" / f"{case_id}.json"
            if not b_path.exists():
                write_json(b_path, review_template(case_id, "REV-B"))
        adjudicated = workspace / "ground-truth" / "adjudicated" / f"{case_id}.json"
        if not adjudicated.exists():
            write_json(adjudicated, ground_truth_template(case_id, review_mode))
        created.append(case_id)
    return {"created_case_ids": created, "review_mode": review_mode}


def _validate_review(payload: dict[str, Any], case_id: str, reviewer_id: str) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != REVIEW_SCHEMA:
        errors.append(f"{case_id}/{reviewer_id}: schema review non valido")
    if payload.get("case_id") != case_id or payload.get("reviewer_id") != reviewer_id:
        errors.append(f"{case_id}/{reviewer_id}: identità review non coerente")
    if payload.get("status") != "complete":
        errors.append(f"{case_id}/{reviewer_id}: review non completata")
    if payload.get("created_without_thistinti_output") is not True:
        errors.append(f"{case_id}/{reviewer_id}: blind declaration mancante")
    return errors


def _validate_truth(payload: dict[str, Any], case_id: str, review_mode: str) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != GROUND_TRUTH_SCHEMA or payload.get("case_id") != case_id:
        errors.append(f"{case_id}: schema o case_id ground truth non coerente")
    if payload.get("created_without_thistinti_output") is not True:
        errors.append(f"{case_id}: ground truth non dichiarata cieca")
    review = payload.get("review", {})
    if review.get("mode") != review_mode:
        errors.append(f"{case_id}: review mode non coerente")
    if review.get("reviewer_a_completed") is not True:
        errors.append(f"{case_id}: revisore A non completato")
    if review_mode == "dual_independent" and review.get("reviewer_b_completed") is not True:
        errors.append(f"{case_id}: revisore B non completato")
    if review_mode.startswith("single_reviewer") and review.get("single_reviewer_limitation") is not True:
        errors.append(f"{case_id}: limite single-reviewer non dichiarato")
    if review.get("adjudication_status") != "sealed":
        errors.append(f"{case_id}: adjudication non sigillata")
    try:
        if int(review.get("disagreement_count", 0)) < 0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append(f"{case_id}: disagreement_count non valido")

    observed = payload.get("observed", {})
    evidence_ids = {
        str(item.get("evidence_id"))
        for item in observed.get("evidence", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    fact_ids: set[str] = set()
    for item in observed.get("facts", []):
        if not isinstance(item, dict):
            errors.append(f"{case_id}: fact non strutturato")
            continue
        fact_id = str(item.get("fact_id", "")).strip()
        if not fact_id:
            errors.append(f"{case_id}: fact_id mancante")
        else:
            fact_ids.add(fact_id)
        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not set(map(str, refs)).issubset(evidence_ids):
            errors.append(f"{case_id}/{fact_id}: evidence_refs mancanti o sconosciuti")
    for item in observed.get("interpretations", []):
        interpretation_id = str(item.get("interpretation_id", "")).strip() if isinstance(item, dict) else ""
        refs = item.get("fact_refs") if isinstance(item, dict) else None
        if not isinstance(refs, list) or not refs or not set(map(str, refs)).issubset(fact_ids):
            errors.append(f"{case_id}/{interpretation_id}: fact_refs mancanti o sconosciuti")
        if not isinstance(item, dict) or not str(item.get("rule_ref", "")).strip():
            errors.append(f"{case_id}/{interpretation_id}: rule_ref obbligatorio")
    for item in payload.get("expected", []):
        if not isinstance(item, dict) or item.get("presence") not in PRESENCE_STATES:
            errors.append(f"{case_id}: presence non valida")
        if not isinstance(item, dict) or item.get("evidentiary_sufficiency") not in SUFFICIENCY_STATES:
            errors.append(f"{case_id}: evidentiary_sufficiency non valida")
    for finding in payload.get("judged", {}).get("findings", []):
        if not isinstance(finding, dict) or finding.get("impact_type") not in IMPACT_TYPES:
            errors.append(f"{case_id}: impact_type non valido")
            continue
        status = finding.get("financial_status")
        if status not in FINANCIAL_STATUSES:
            errors.append(f"{case_id}: financial_status non valido")
        if finding["impact_type"] != "financial" and status != "not_applicable":
            errors.append(f"{case_id}: financial_status incoerente con impatto non finanziario")
    return errors


def seal_ground_truth(workspace: Path) -> dict[str, Any]:
    manifest, errors = verify_manifest_seal(workspace)
    if errors:
        raise ValueError("manifest non integro:\n- " + "\n- ".join(errors))
    results_path = workspace / "results" / "blind-results.csv"
    if results_path.is_file():
        with results_path.open(newline="", encoding="utf-8") as handle:
            if list(csv.DictReader(handle)):
                raise ValueError("ground truth non sigillabile dopo la registrazione dei risultati")

    review_mode = manifest["review"]["mode"]
    case_hashes: dict[str, Any] = {}
    validation_errors: list[str] = []
    disagreement_total = 0
    for case_id in manifest["case_register"]["blind_case_ids"]:
        a_path = workspace / "ground-truth" / "reviewer-a" / f"{case_id}.json"
        if not a_path.is_file():
            validation_errors.append(f"{case_id}: review REV-A mancante")
            continue
        validation_errors.extend(_validate_review(read_json(a_path), case_id, "REV-A"))
        b_path: Path | None = None
        if review_mode == "dual_independent":
            b_path = workspace / "ground-truth" / "reviewer-b" / f"{case_id}.json"
            if not b_path.is_file():
                validation_errors.append(f"{case_id}: review REV-B mancante")
                continue
            validation_errors.extend(_validate_review(read_json(b_path), case_id, "REV-B"))
        adjudicated = workspace / "ground-truth" / "adjudicated" / f"{case_id}.json"
        if not adjudicated.is_file():
            validation_errors.append(f"{case_id}: ground truth adjudicata mancante")
            continue
        payload = read_json(adjudicated)
        validation_errors.extend(_validate_truth(payload, case_id, review_mode))
        disagreement_total += int(payload.get("review", {}).get("disagreement_count", 0) or 0)
        hashes = {
            "reviewer_a_sha256": sha256_file(a_path),
            "adjudicated_sha256": sha256_file(adjudicated),
        }
        if b_path is not None:
            hashes["reviewer_b_sha256"] = sha256_file(b_path)
        case_hashes[case_id] = hashes
    if validation_errors:
        raise ValueError("ground truth non sigillabile:\n- " + "\n- ".join(validation_errors))

    canonical = (
        "\n".join(case_id + ":" + json.dumps(case_hashes[case_id], sort_keys=True) for case_id in sorted(case_hashes))
        + "\n"
    )
    seal = {
        "schema": SEAL_SCHEMA,
        "kind": "ground_truth",
        "pilot_id": manifest["pilot_id"],
        "sealed_at": utc_now(),
        "review_mode": review_mode,
        "blind_case_count": len(case_hashes),
        "reviewer_disagreement_count": disagreement_total,
        "private_document_hashes_published": False,
        "case_hashes": case_hashes,
        "aggregate_sha256": sha256_text(canonical),
    }
    write_json(workspace / "ground-truth.seal.json", seal)
    return seal


def check_ready(workspace: Path) -> dict[str, Any]:
    manifest, errors = verify_manifest_seal(workspace)
    seal_path = workspace / "ground-truth.seal.json"
    if not seal_path.is_file():
        errors.append("ground-truth.seal.json mancante")
    else:
        seal = read_json(seal_path)
        expected_ids = set(manifest.get("case_register", {}).get("blind_case_ids", []))
        if seal.get("kind") != "ground_truth" or set(seal.get("case_hashes", {})) != expected_ids:
            errors.append("ground truth seal non copre esattamente il blind set")
        for case_id, hashes in seal.get("case_hashes", {}).items():
            paths = {
                "reviewer_a_sha256": workspace / "ground-truth" / "reviewer-a" / f"{case_id}.json",
                "adjudicated_sha256": workspace / "ground-truth" / "adjudicated" / f"{case_id}.json",
            }
            if "reviewer_b_sha256" in hashes:
                paths["reviewer_b_sha256"] = workspace / "ground-truth" / "reviewer-b" / f"{case_id}.json"
            for key, path in paths.items():
                if not path.is_file() or hashes.get(key) != sha256_file(path):
                    errors.append(f"{case_id}: ground truth modificata dopo il seal")
    report = {
        "schema": "thistinti.procurement-pilot-readiness.v1",
        "pilot_id": manifest.get("pilot_id"),
        "generated_at": utc_now(),
        "errors": sorted(set(errors)),
        "ready_for_blind_run": not errors,
        "rule": (
            "Se ready_for_blind_run è false, il blind run non è metodologicamente valido. "
            "Qualsiasi modifica a un artefatto congelato richiede un nuovo Manifest."
        ),
    }
    write_json(workspace / "readiness.json", report)
    return report
