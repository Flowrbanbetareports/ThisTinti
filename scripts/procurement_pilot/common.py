from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any

PLAN_SCHEMA = "thistinti.procurement-pilot-plan.v1"
MANIFEST_SCHEMA = "thistinti.procurement-pilot-manifest.v1"
GROUND_TRUTH_SCHEMA = "thistinti.procurement-ground-truth.v1"
REVIEW_SCHEMA = "thistinti.procurement-ground-truth-review.v1"
SEAL_SCHEMA = "thistinti.procurement-pilot-seal.v1"
RESULT_SCHEMA = "thistinti.procurement-pilot-result.v1"
PRIVATE_INVENTORY_SCHEMA = "thistinti.procurement-private-document-inventory.v1"

MIN_CALIBRATION = 5
MAX_CALIBRATION = 10
MIN_BLIND = 20
MAX_BLIND = 25
REVIEW_MODES = {"dual_independent", "single_reviewer_with_declared_limitation"}

PRESENCE_STATES = {
    "present",
    "not_found",
    "pending",
    "not_applicable",
    "indeterminate",
    "substituted",
}
SUFFICIENCY_STATES = {
    "sufficient",
    "partial",
    "insufficient",
    "contradictory",
    "not_verifiable",
}
IMPACT_TYPES = {"informational", "non_financial", "financial"}
FINANCIAL_STATUSES = {
    "unknown",
    "potential",
    "confirmed_loss",
    "avoided_loss",
    "not_applicable",
}

CASE_REGISTER_FIELDS = [
    "case_id",
    "phase",
    "authorized",
    "source_alias",
    "template_family",
    "similarity_group",
    "case_type",
    "notes",
]
RESULT_FIELDS = [
    "case_id",
    "true_positives",
    "false_positives",
    "false_negatives",
    "critical_miss",
    "potential_exposure_detected",
    "potential_exposure_missed",
    "confirmed_loss",
    "avoided_loss",
    "currency",
    "notes",
]
BACKLOG_FIELDS = [
    "case_id",
    "error_type",
    "severity",
    "description",
    "correction_target",
    "status",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(f"{label} mancante: {path}")
    return path


def parse_bool(value: str, field: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes", "si", "sì"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{field}: booleano non valido")


def parse_non_negative_int(value: str, field: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field}: deve essere >= 0")
    return parsed


def parse_non_negative_float(value: str, field: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field}: deve essere >= 0 e finito")
    return parsed


def load_case_register(workspace: Path) -> list[dict[str, str]]:
    path = require_file(workspace / "case-register.csv", "case-register.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CASE_REGISTER_FIELDS:
            raise ValueError("intestazioni case-register.csv non valide")
        return list(reader)


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float | None, float | None]:
    if total <= 0:
        return (None, None)
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) / total) + z * z / (4 * total * total)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))
