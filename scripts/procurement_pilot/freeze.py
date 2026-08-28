from __future__ import annotations

from pathlib import Path
from typing import Any

from procurement_pilot.common import (
    MANIFEST_SCHEMA,
    PLAN_SCHEMA,
    PRIVATE_INVENTORY_SCHEMA,
    SEAL_SCHEMA,
    load_case_register,
    read_json,
    require_file,
    sha256_file,
    utc_now,
    write_json,
)
from procurement_pilot.workspace import validate_case_register, validate_preregistration


PROVENANCE_MATRIX_SCHEMA = "thistinti.procurement-provenance-matrix.v1"
PROVENANCE_STATUSES = {"complete", "incomplete", "unsupported"}


def _public_artifact_record(path: Path, version: str, label: str) -> dict[str, Any]:
    require_file(path, label)
    if not version.strip():
        raise ValueError(f"{label}: versione obbligatoria")
    return {"version": version.strip(), "ref": path.name, "sha256": sha256_file(path)}


def _validate_provenance_matrix(rule_pack_path: Path, matrix_path: Path, matrix_version: str) -> None:
    rule_pack = read_json(require_file(rule_pack_path, "Rule Pack"))
    matrix = read_json(require_file(matrix_path, "Provenance Matrix"))
    if matrix.get("schema") != PROVENANCE_MATRIX_SCHEMA:
        raise ValueError("Provenance Matrix: schema non valido")
    if str(matrix.get("version") or "") != matrix_version.strip():
        raise ValueError("Provenance Matrix: versione dichiarata diversa dall'artefatto")
    if matrix.get("rule_pack_id") != rule_pack.get("rule_pack_id"):
        raise ValueError("Provenance Matrix: rule_pack_id non corrisponde al Rule Pack")
    if str(matrix.get("rule_pack_version") or "") != str(rule_pack.get("version") or ""):
        raise ValueError("Provenance Matrix: versione Rule Pack non corrispondente")

    declared_families: dict[str, list[str]] = {}
    for family in rule_pack.get("rule_families") or []:
        family_id = str(family.get("id") or "")
        if not family_id or family_id in declared_families:
            raise ValueError("Rule Pack: famiglie mancanti o duplicate")
        case_types = family.get("engine_case_types")
        if not isinstance(case_types, list) or any(not isinstance(value, str) or not value for value in case_types):
            raise ValueError(f"Rule Pack: engine_case_types non validi per {family_id}")
        declared_families[family_id] = case_types

    matrix_families: dict[str, dict[str, Any]] = {}
    for family in matrix.get("families") or []:
        family_id = str(family.get("id") or "")
        status = family.get("provenance_status")
        if not family_id or family_id in matrix_families or status not in PROVENANCE_STATUSES:
            raise ValueError("Provenance Matrix: famiglie mancanti, duplicate o con stato non valido")
        case_types = family.get("case_types")
        if not isinstance(case_types, list):
            raise ValueError(f"Provenance Matrix: case_types non validi per {family_id}")
        matrix_families[family_id] = family

    if set(matrix_families) != set(declared_families):
        raise ValueError("Provenance Matrix: famiglie diverse dal Rule Pack")
    for family_id, case_types in declared_families.items():
        if matrix_families[family_id].get("case_types") != case_types:
            raise ValueError(f"Provenance Matrix: case_type diversi dal Rule Pack per {family_id}")

    expected_pairs = {
        (family_id, case_type) for family_id, case_types in declared_families.items() for case_type in case_types
    }
    rules = matrix.get("rules") or []
    actual_pairs: set[tuple[str, str]] = set()
    blockers: list[str] = []
    for rule in rules:
        family_id = str(rule.get("family") or "")
        case_type = str(rule.get("case_type") or "")
        status = rule.get("provenance_status")
        pair = (family_id, case_type)
        if not family_id or not case_type or pair in actual_pairs or status not in {"complete", "incomplete"}:
            raise ValueError("Provenance Matrix: regole mancanti, duplicate o con stato non valido")
        actual_pairs.add(pair)
        blind_eligible = rule.get("blind_eligible") is True
        if blind_eligible != (status == "complete"):
            raise ValueError(f"Provenance Matrix: blind_eligible incoerente per {case_type}")
        if not blind_eligible:
            blockers.append(case_type)
    if actual_pairs != expected_pairs:
        raise ValueError("Provenance Matrix: elenco regole diverso dal Rule Pack")

    unsupported = sorted(
        family_id for family_id, family in matrix_families.items() if family.get("provenance_status") == "unsupported"
    )
    declared_readiness = matrix.get("blind_readiness") or {}
    expected_ready = not blockers and not unsupported
    if declared_readiness.get("ready") is not expected_ready:
        raise ValueError("Provenance Matrix: blind_readiness incoerente con le regole")
    if sorted(declared_readiness.get("blocking_case_types") or []) != sorted(blockers):
        raise ValueError("Provenance Matrix: blocking_case_types incoerenti")
    if sorted(declared_readiness.get("unsupported_families") or []) != unsupported:
        raise ValueError("Provenance Matrix: unsupported_families incoerenti")
    if not expected_ready:
        details = []
        if blockers:
            details.append("provenance incompleta: " + ", ".join(sorted(blockers)))
        if unsupported:
            details.append("famiglie non supportate: " + ", ".join(unsupported))
        raise ValueError("freeze bloccato dalla Provenance Matrix: " + "; ".join(details))


def freeze_workspace(
    workspace: Path,
    *,
    software_commit: str,
    software_version: str,
    practice_model: Path,
    practice_model_version: str,
    rule_pack: Path,
    rule_pack_version: str,
    provenance_matrix: Path,
    provenance_matrix_version: str,
    company_profile: Path,
    company_profile_version: str,
    ground_truth_protocol: Path,
    ground_truth_protocol_version: str,
    evaluation_protocol: Path,
    evaluation_protocol_version: str,
) -> dict[str, Any]:
    plan = read_json(require_file(workspace / "pilot-plan.json", "pilot-plan.json"))
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("schema pilot-plan non valido")
    rows = load_case_register(workspace)
    errors = validate_preregistration(plan) + validate_case_register(plan, rows)
    if errors:
        raise ValueError("freeze bloccato:\n- " + "\n- ".join(errors))
    if not software_commit.strip() or not software_version.strip():
        raise ValueError("software_commit e software_version sono obbligatori")

    inventory_path = workspace / "private" / "document-inventory.json"
    inventory = read_json(require_file(inventory_path, "private/document-inventory.json"))
    if inventory.get("schema") != PRIVATE_INVENTORY_SCHEMA:
        raise ValueError("schema private document inventory non valido")
    if inventory.get("cases_without_documents"):
        raise ValueError(
            "inventory-private: pratiche senza documenti: " + ", ".join(inventory["cases_without_documents"])
        )

    _validate_provenance_matrix(rule_pack, provenance_matrix, provenance_matrix_version)

    artifacts = {
        "practice_model": (practice_model, practice_model_version, "Practice Model"),
        "rule_pack": (rule_pack, rule_pack_version, "Rule Pack"),
        "provenance_matrix": (provenance_matrix, provenance_matrix_version, "Provenance Matrix"),
        "company_profile": (company_profile, company_profile_version, "Company Profile"),
        "ground_truth_protocol": (
            ground_truth_protocol,
            ground_truth_protocol_version,
            "Ground Truth Protocol",
        ),
        "evaluation_protocol": (
            evaluation_protocol,
            evaluation_protocol_version,
            "Evaluation Protocol",
        ),
    }
    public_records: dict[str, Any] = {}
    private_locations: dict[str, Any] = {
        "schema": "thistinti.procurement-private-frozen-artifact-locations.v1",
        "pilot_id": plan["pilot_id"],
        "private": True,
        "must_not_be_published": True,
        "artifacts": {},
    }
    for key, (path, version, label) in artifacts.items():
        public_records[key] = _public_artifact_record(path, version, label)
        private_locations["artifacts"][key] = {
            "path": str(path.resolve()),
            "sha256": public_records[key]["sha256"],
        }
    write_json(workspace / "private" / "frozen-artifact-locations.json", private_locations)

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "pilot_id": plan["pilot_id"],
        "created_at": plan["created_at"],
        "frozen_at": utc_now(),
        "domain": "procurement",
        "organization_alias": plan["organization_alias"],
        "methodology": plan["methodology"],
        "preregistration": plan["preregistration"],
        "review": plan["review"],
        "privacy": plan["privacy"],
        "case_register": {
            "ref": "case-register.csv",
            "sha256": sha256_file(workspace / "case-register.csv"),
            "calibration_case_ids": [r["case_id"] for r in rows if r["phase"] == "calibration"],
            "blind_case_ids": [r["case_id"] for r in rows if r["phase"] == "blind"],
        },
        "private_document_inventory": {
            "ref": "private/document-inventory.json",
            "sha256": sha256_file(inventory_path),
            "document_hashes_published": False,
        },
        "frozen_artifacts": {
            "software": {"commit": software_commit.strip(), "version": software_version.strip()},
            **public_records,
        },
        "claim_boundary": plan["claim_boundary"],
        "invalidation_rule": (
            "Qualsiasi modifica a software, Practice Model, Rule Pack, Provenance Matrix, Company Profile, "
            "Ground Truth Protocol, Evaluation Protocol, case-register o ground truth "
            "chiude questo run. Serve un nuovo Manifest; i risultati non possono essere mescolati."
        ),
    }
    manifest_path = workspace / "pilot-manifest.json"
    write_json(manifest_path, manifest)
    write_json(
        workspace / "pilot-manifest.seal.json",
        {
            "schema": SEAL_SCHEMA,
            "kind": "pilot_manifest",
            "pilot_id": manifest["pilot_id"],
            "sealed_at": utc_now(),
            "ref": "pilot-manifest.json",
            "sha256": sha256_file(manifest_path),
        },
    )
    return manifest


def verify_manifest_seal(workspace: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    manifest_path = require_file(workspace / "pilot-manifest.json", "pilot-manifest.json")
    seal_path = require_file(workspace / "pilot-manifest.seal.json", "pilot-manifest.seal.json")
    manifest = read_json(manifest_path)
    seal = read_json(seal_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("schema manifest non valido")
    if seal.get("kind") != "pilot_manifest":
        errors.append("tipo seal manifest non valido")
    if seal.get("sha256") != sha256_file(manifest_path):
        errors.append("pilot-manifest.json modificato dopo il freeze")

    case_path = workspace / "case-register.csv"
    if not case_path.is_file() or manifest.get("case_register", {}).get("sha256") != sha256_file(case_path):
        errors.append("case-register.csv modificato dopo il freeze")
    inventory_path = workspace / "private" / "document-inventory.json"
    if not inventory_path.is_file() or manifest.get("private_document_inventory", {}).get("sha256") != sha256_file(
        inventory_path
    ):
        errors.append("private document inventory modificato dopo il freeze")

    locations_path = workspace / "private" / "frozen-artifact-locations.json"
    if not locations_path.is_file():
        errors.append("private frozen artifact locations mancante")
        return manifest, errors
    locations = read_json(locations_path).get("artifacts", {})
    for key in [
        "practice_model",
        "rule_pack",
        "provenance_matrix",
        "company_profile",
        "ground_truth_protocol",
        "evaluation_protocol",
    ]:
        record = manifest.get("frozen_artifacts", {}).get(key, {})
        location = locations.get(key, {})
        path = Path(str(location.get("path", "")))
        if not path.is_file():
            errors.append(f"{key}: artefatto congelato non raggiungibile")
            continue
        actual = sha256_file(path)
        if record.get("sha256") != actual or location.get("sha256") != actual:
            errors.append(f"{key}: artefatto modificato dopo il freeze")
    return manifest, errors
