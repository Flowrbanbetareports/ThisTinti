from __future__ import annotations

from collections import Counter
from datetime import date
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import add_audit
from ..models import DiscrepancyCase, utcnow
from ..rc15_models import RC15CompanyProfileVersion, RC15PilotCase, RC15PilotWorkspace, RC15Practice
from ..version import RELEASE_VERSION
from .rc15 import (
    _canonical_json,
    _json,
    _practice_documents,
    _sha,
    company_profile_payload,
    ensure_company_profile,
)


def create_pilot(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    *,
    name: str,
    authorization_reference: str,
    reviewer_primary: str,
    reviewer_secondary: str,
    scope: str,
    retention_end: date | None,
) -> RC15PilotWorkspace:
    primary = reviewer_primary.strip()
    secondary = reviewer_secondary.strip()
    if primary.casefold() == secondary.casefold():
        raise ValueError("Servono due revisori distinti")
    version = (
        int(
            db.scalar(
                select(func.coalesce(func.max(RC15PilotWorkspace.version), 0)).where(
                    RC15PilotWorkspace.tenant_id == tenant_id,
                    RC15PilotWorkspace.name == name.strip(),
                )
            )
            or 0
        )
        + 1
    )
    profile = ensure_company_profile(db, tenant_id, user_id)
    item = RC15PilotWorkspace(
        tenant_id=tenant_id,
        name=name.strip(),
        version=version,
        authorization_reference=authorization_reference.strip(),
        reviewer_primary=primary,
        reviewer_secondary=secondary,
        scope=scope.strip(),
        retention_end=retention_end,
        profile_version_id=profile.id,
        created_by=user_id,
    )
    db.add(item)
    db.flush()
    add_audit(
        db,
        tenant_id,
        "rc15.pilot_created",
        user_id,
        "rc15_pilot",
        item.id,
        {"name": item.name, "version": item.version, "profile_version": profile.version},
    )
    return item


def _pilot_case_payload(item: RC15PilotCase, *, include_ground_truth: bool) -> dict[str, Any]:
    result = {
        "id": item.id,
        "practice_id": item.practice_id,
        "manual_seconds": item.manual_seconds,
        "assisted_seconds": item.assisted_seconds,
        "user_score": item.user_score,
        "notes": item.notes,
        "updated_at": item.updated_at.isoformat(),
    }
    if include_ground_truth:
        result.update(
            {
                "reviewer_primary": _json(item.reviewer_primary_json, {}),
                "reviewer_secondary": _json(item.reviewer_secondary_json, {}),
                "adjudicated": _json(item.adjudicated_json, {}),
            }
        )
    else:
        primary = _json(item.reviewer_primary_json, {})
        secondary = _json(item.reviewer_secondary_json, {})
        result["blind_reviews_recorded"] = bool(primary) and bool(secondary)
        result["reviewer_disagreement"] = bool(primary) and bool(secondary) and _sha(primary) != _sha(secondary)
        result["adjudication_recorded"] = bool(_json(item.adjudicated_json, {}))
    return result


def pilot_payload(
    db: Session, tenant_id: str, item: RC15PilotWorkspace, *, include_ground_truth: bool = False
) -> dict[str, Any]:
    cases = list(
        db.scalars(
            select(RC15PilotCase)
            .where(RC15PilotCase.tenant_id == tenant_id, RC15PilotCase.pilot_id == item.id)
            .order_by(RC15PilotCase.created_at)
        )
    )
    profile = (
        db.scalar(
            select(RC15CompanyProfileVersion).where(
                RC15CompanyProfileVersion.id == item.profile_version_id,
                RC15CompanyProfileVersion.tenant_id == tenant_id,
            )
        )
        if item.profile_version_id
        else None
    )
    result = _json(item.result_json, {})
    return {
        "id": item.id,
        "name": item.name,
        "version": item.version,
        "status": item.status,
        "authorization_reference": item.authorization_reference if include_ground_truth else None,
        "reviewers": [item.reviewer_primary, item.reviewer_secondary] if include_ground_truth else ["REV-A", "REV-B"],
        "scope": item.scope,
        "retention_end": item.retention_end.isoformat() if item.retention_end else None,
        "profile": company_profile_payload(profile),
        "ground_truth_hash": item.ground_truth_hash,
        "engine_version": item.engine_version,
        "frozen_at": item.frozen_at.isoformat() if item.frozen_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "case_count": len(cases),
        "measurement_complete_count": sum(
            case.manual_seconds is not None and case.assisted_seconds is not None and case.user_score is not None
            for case in cases
        ),
        "result": result,
        "cases": [_pilot_case_payload(case, include_ground_truth=include_ground_truth) for case in cases],
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def add_pilot_practice(
    db: Session,
    tenant_id: str,
    pilot_id: str,
    practice_id: str,
) -> RC15PilotCase:
    pilot = db.scalar(
        select(RC15PilotWorkspace).where(RC15PilotWorkspace.id == pilot_id, RC15PilotWorkspace.tenant_id == tenant_id)
    )
    if pilot is None:
        raise LookupError("Pilot non trovato")
    if pilot.status != "draft":
        raise ValueError("Le pratiche possono essere aggiunte soltanto prima del congelamento")
    practice = db.scalar(
        select(RC15Practice).where(
            RC15Practice.id == practice_id,
            RC15Practice.tenant_id == tenant_id,
            RC15Practice.status != "deleted",
        )
    )
    if practice is None:
        raise LookupError("Pratica non trovata")
    existing = db.scalar(
        select(RC15PilotCase).where(
            RC15PilotCase.tenant_id == tenant_id,
            RC15PilotCase.pilot_id == pilot_id,
            RC15PilotCase.practice_id == practice_id,
        )
    )
    if existing:
        return existing
    item = RC15PilotCase(tenant_id=tenant_id, pilot_id=pilot_id, practice_id=practice_id)
    db.add(item)
    db.flush()
    return item


def update_pilot_case(
    db: Session,
    tenant_id: str,
    pilot_id: str,
    pilot_case_id: str,
    *,
    reviewer_primary: dict[str, Any] | None,
    reviewer_secondary: dict[str, Any] | None,
    adjudicated: dict[str, Any] | None,
    manual_seconds: float | None,
    assisted_seconds: float | None,
    user_score: int | None,
    notes: str | None,
) -> RC15PilotCase:
    pilot = db.scalar(
        select(RC15PilotWorkspace).where(RC15PilotWorkspace.id == pilot_id, RC15PilotWorkspace.tenant_id == tenant_id)
    )
    item = db.scalar(
        select(RC15PilotCase).where(
            RC15PilotCase.id == pilot_case_id,
            RC15PilotCase.tenant_id == tenant_id,
            RC15PilotCase.pilot_id == pilot_id,
        )
    )
    if pilot is None or item is None:
        raise LookupError("Caso pilot non trovato")
    if pilot.status == "archived":
        raise ValueError("Pilot archiviato")
    reviewer_changes = any(value is not None for value in (reviewer_primary, reviewer_secondary))
    if reviewer_changes and pilot.status != "draft":
        raise ValueError("Le revisioni indipendenti sono congelate; crea una nuova versione del pilot per correggerle")
    if adjudicated is not None and pilot.status != "frozen":
        raise ValueError("L’adjudication è consentita soltanto dopo il congelamento cieco e prima dell’esecuzione")
    if reviewer_primary is not None:
        item.reviewer_primary_json = _canonical_json(reviewer_primary)
    if reviewer_secondary is not None:
        item.reviewer_secondary_json = _canonical_json(reviewer_secondary)
    if adjudicated is not None:
        item.adjudicated_json = _canonical_json(adjudicated)
    if manual_seconds is not None:
        if manual_seconds <= 0:
            raise ValueError("manual_seconds deve essere maggiore di zero")
        item.manual_seconds = manual_seconds
    if assisted_seconds is not None:
        if assisted_seconds <= 0:
            raise ValueError("assisted_seconds deve essere maggiore di zero")
        item.assisted_seconds = assisted_seconds
    if user_score is not None:
        if user_score not in {1, 2, 3, 4, 5}:
            raise ValueError("user_score deve essere tra 1 e 5")
        item.user_score = user_score
    if notes is not None:
        item.notes = notes.strip() or None
    item.updated_at = utcnow()
    db.flush()
    return item


def _practice_freeze_snapshot(db: Session, tenant_id: str, practice_id: str) -> dict[str, Any]:
    practice = db.scalar(
        select(RC15Practice).where(
            RC15Practice.id == practice_id,
            RC15Practice.tenant_id == tenant_id,
            RC15Practice.status != "deleted",
        )
    )
    if practice is None or not practice.chain_id:
        raise ValueError("Pratica del pilot non disponibile")
    linked = _practice_documents(db, tenant_id, practice.chain_id)
    return {
        "practice_id": practice.id,
        "chain_id": practice.chain_id,
        "document_hashes": sorted(document.file_hash for _link, document in linked),
        "profile_version_id": practice.profile_version_id,
    }


def freeze_pilot(db: Session, tenant_id: str, user_id: str | None, pilot_id: str) -> RC15PilotWorkspace:
    pilot = db.scalar(
        select(RC15PilotWorkspace).where(RC15PilotWorkspace.id == pilot_id, RC15PilotWorkspace.tenant_id == tenant_id)
    )
    if pilot is None:
        raise LookupError("Pilot non trovato")
    if pilot.status != "draft":
        raise ValueError("Il pilot non è più modificabile")
    cases = list(
        db.scalars(
            select(RC15PilotCase)
            .where(RC15PilotCase.tenant_id == tenant_id, RC15PilotCase.pilot_id == pilot.id)
            .order_by(RC15PilotCase.practice_id)
        )
    )
    if len(cases) < 30:
        raise ValueError("Il pilot reale richiede almeno 30 pratiche indipendenti")
    case_manifest: list[dict[str, Any]] = []
    for item in cases:
        primary = _json(item.reviewer_primary_json, {})
        secondary = _json(item.reviewer_secondary_json, {})
        if not primary or not secondary:
            raise ValueError(f"Revisioni indipendenti incomplete per la pratica {item.practice_id}")
        snapshot = _practice_freeze_snapshot(db, tenant_id, item.practice_id)
        case_manifest.append(
            {
                **snapshot,
                "reviewer_primary_hash": _sha(primary),
                "reviewer_secondary_hash": _sha(secondary),
                "reviewers_agree": _sha(primary) == _sha(secondary),
            }
        )
    profile = (
        db.scalar(
            select(RC15CompanyProfileVersion).where(
                RC15CompanyProfileVersion.id == pilot.profile_version_id,
                RC15CompanyProfileVersion.tenant_id == tenant_id,
            )
        )
        if pilot.profile_version_id
        else None
    )
    manifest = {
        "schema": "thistinti.rc15.pilot-freeze.v1",
        "name": pilot.name,
        "version": pilot.version,
        "authorization_reference": pilot.authorization_reference,
        "reviewers": [pilot.reviewer_primary, pilot.reviewer_secondary],
        "scope": pilot.scope,
        "engine_version": RELEASE_VERSION,
        "profile_hash": profile.config_hash if profile else None,
        "cases": case_manifest,
    }
    pilot.ground_truth_hash = _sha(manifest)
    pilot.freeze_manifest_json = _canonical_json(manifest)
    pilot.engine_version = RELEASE_VERSION
    pilot.frozen_at = utcnow()
    pilot.status = "frozen"
    add_audit(
        db,
        tenant_id,
        "rc15.pilot_frozen",
        user_id,
        "rc15_pilot",
        pilot.id,
        {"ground_truth_hash": pilot.ground_truth_hash, "case_count": len(cases), "engine_version": RELEASE_VERSION},
    )
    db.flush()
    return pilot


def _expected_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    findings = payload.get("findings", [])
    return findings if isinstance(findings, list) else []


def run_pilot(db: Session, tenant_id: str, user_id: str | None, pilot_id: str) -> RC15PilotWorkspace:
    pilot = db.scalar(
        select(RC15PilotWorkspace).where(RC15PilotWorkspace.id == pilot_id, RC15PilotWorkspace.tenant_id == tenant_id)
    )
    if pilot is None:
        raise LookupError("Pilot non trovato")
    if pilot.status not in {"frozen", "completed"}:
        raise ValueError("Il pilot deve essere congelato prima dell'esecuzione")
    if pilot.engine_version != RELEASE_VERSION:
        raise ValueError("La versione dell'app è cambiata dopo il congelamento: crea una nuova versione del pilot")
    manifest = _json(pilot.freeze_manifest_json, {})
    if not manifest or pilot.ground_truth_hash != _sha(manifest):
        raise ValueError("Manifest del pilot non integro")
    manifest_cases = {item["practice_id"]: item for item in manifest.get("cases", []) if isinstance(item, dict)}
    cases = list(
        db.scalars(
            select(RC15PilotCase)
            .where(RC15PilotCase.tenant_id == tenant_id, RC15PilotCase.pilot_id == pilot.id)
            .order_by(RC15PilotCase.practice_id)
        )
    )
    tp = fp = fn = critical_misses = 0
    disagreements = 0
    scenario_results: list[dict[str, Any]] = []
    manual_times: list[float] = []
    assisted_times: list[float] = []
    user_scores: list[int] = []
    measurement_missing = 0
    pilot.status = "running"
    db.flush()
    for item in cases:
        frozen = manifest_cases.get(item.practice_id)
        if not frozen:
            raise ValueError("Manifest congelato incompleto")
        current_snapshot = _practice_freeze_snapshot(db, tenant_id, item.practice_id)
        for key in ("chain_id", "document_hashes", "profile_version_id"):
            if current_snapshot.get(key) != frozen.get(key):
                raise ValueError(f"La pratica {item.practice_id} è cambiata dopo il congelamento")
        primary = _json(item.reviewer_primary_json, {})
        secondary = _json(item.reviewer_secondary_json, {})
        if _sha(primary) != frozen.get("reviewer_primary_hash") or _sha(secondary) != frozen.get(
            "reviewer_secondary_hash"
        ):
            raise ValueError(f"Le revisioni cieche della pratica {item.practice_id} sono cambiate dopo il congelamento")
        if _sha(primary) == _sha(secondary):
            adjudicated = primary
        else:
            adjudicated = _json(item.adjudicated_json, {})
            if not adjudicated:
                raise ValueError(f"Adjudication mancante per la pratica {item.practice_id}")
        expected = _expected_findings(adjudicated)
        expected_counter = Counter(str(entry.get("case_type")) for entry in expected if entry.get("case_type"))
        practice = db.scalar(
            select(RC15Practice).where(RC15Practice.id == item.practice_id, RC15Practice.tenant_id == tenant_id)
        )
        actual_cases = list(
            db.scalars(
                select(DiscrepancyCase).where(
                    DiscrepancyCase.tenant_id == tenant_id,
                    DiscrepancyCase.chain_id == practice.chain_id,
                    DiscrepancyCase.status != "superseded",
                )
            )
        )
        actual_counter = Counter(case.case_type for case in actual_cases)
        case_tp = sum(
            min(expected_counter[key], actual_counter[key]) for key in set(expected_counter) | set(actual_counter)
        )
        case_fp = sum(max(actual_counter[key] - expected_counter[key], 0) for key in actual_counter)
        case_fn = sum(max(expected_counter[key] - actual_counter[key], 0) for key in expected_counter)
        critical_expected = Counter(
            str(entry.get("case_type"))
            for entry in expected
            if entry.get("case_type") and str(entry.get("severity", "")).casefold() == "critical"
        )
        case_critical_misses = sum(max(critical_expected[key] - actual_counter[key], 0) for key in critical_expected)
        tp += case_tp
        fp += case_fp
        fn += case_fn
        critical_misses += case_critical_misses
        disagreements += int(_sha(primary) != _sha(secondary))
        if item.manual_seconds is None or item.assisted_seconds is None or item.user_score is None:
            measurement_missing += 1
        else:
            manual_times.append(float(item.manual_seconds))
            assisted_times.append(float(item.assisted_seconds))
            user_scores.append(int(item.user_score))
        scenario_results.append(
            {
                "practice_id": item.practice_id,
                "true_positives": case_tp,
                "false_positives": case_fp,
                "false_negatives": case_fn,
                "critical_misses": case_critical_misses,
                "adjudication_hash": _sha(adjudicated),
            }
        )
    precision = tp / (tp + fp) if tp + fp else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    total_manual = sum(manual_times)
    total_assisted = sum(assisted_times)
    saved = total_manual - total_assisted
    if measurement_missing:
        decision = "incompleto"
    elif critical_misses:
        decision = "non_idoneo"
    elif fn:
        decision = "idoneo_solo_con_revisione_rafforzata"
    else:
        decision = "idoneo_con_revisione_umana"
    result = {
        "schema": "thistinti.rc15.pilot-result.v1",
        "generated_at": utcnow().isoformat(),
        "engine_version": RELEASE_VERSION,
        "ground_truth_hash": pilot.ground_truth_hash,
        "case_count": len(cases),
        "metrics": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "critical_misses": critical_misses,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "reviewer_disagreements": disagreements,
            "measurement_missing": measurement_missing,
            "manual_total_seconds": round(total_manual, 3),
            "assisted_total_seconds": round(total_assisted, 3),
            "time_saved_seconds": round(saved, 3),
            "time_saved_percent": round((saved / total_manual * 100), 2) if total_manual else None,
            "manual_mean_seconds": round(mean(manual_times), 3) if manual_times else None,
            "assisted_mean_seconds": round(mean(assisted_times), 3) if assisted_times else None,
            "average_user_score": round(mean(user_scores), 2) if user_scores else None,
        },
        "decision": decision,
        "scenarios": scenario_results,
        "claim_boundary": {
            "production_certification": False,
            "legal_or_accounting_certification": False,
            "automatic_external_actions_allowed": False,
            "human_review_required": True,
        },
    }
    pilot.result_json = _canonical_json(result)
    if measurement_missing:
        pilot.status = "frozen"
        pilot.completed_at = None
    else:
        pilot.status = "completed"
        pilot.completed_at = utcnow()
    add_audit(
        db,
        tenant_id,
        "rc15.pilot_run_completed",
        user_id,
        "rc15_pilot",
        pilot.id,
        {"decision": decision, "precision": precision, "recall": recall, "f1": f1},
    )
    db.flush()
    return pilot


def render_pilot_markdown(item: RC15PilotWorkspace) -> str:
    result = _json(item.result_json, {})
    metrics = result.get("metrics") or {}
    lines = [
        f"# ThisTinti RC15 — Pilot {item.name} v{item.version}",
        "",
        f"- Versione motore: `{item.engine_version or '—'}`",
        f"- Ground truth SHA-256: `{item.ground_truth_hash or '—'}`",
        f"- Stato: `{item.status}`",
        f"- Decisione: `{result.get('decision', 'non eseguito')}`",
        "",
        "## Metriche",
        "",
        f"- Precision: {metrics.get('precision', '—')}",
        f"- Recall: {metrics.get('recall', '—')}",
        f"- F1: {metrics.get('f1', '—')}",
        f"- Falsi positivi: {metrics.get('false_positives', '—')}",
        f"- Falsi negativi: {metrics.get('false_negatives', '—')}",
        f"- Errori critici non rilevati: {metrics.get('critical_misses', '—')}",
        f"- Tempo risparmiato: {metrics.get('time_saved_percent', '—')}%",
        f"- Voto utilizzatore medio: {metrics.get('average_user_score', '—')}",
        "",
        "## Limiti",
        "",
        "Questo rapporto misura il pilot congelato indicato dall'hash. Non è una certificazione legale, contabile, di sicurezza o di produzione e non autorizza azioni economiche automatiche.",
        "",
    ]
    return "\n".join(lines)
