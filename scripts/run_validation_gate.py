#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import Tenant, ValidationDataset  # noqa: E402
from app.schemas import ValidationDatasetPayload  # noqa: E402
from app.services.validation import run_validation_dataset  # noqa: E402


def main() -> int:
    payload = ValidationDatasetPayload.model_validate_json(
        (ROOT / "samples" / "validation_core.json").read_text(encoding="utf-8")
    )
    db = SessionLocal()
    tenant = Tenant(name="ThisTinti CI Validation", status="active")
    try:
        db.add(tenant)
        db.flush()
        dataset = ValidationDataset(
            tenant_id=tenant.id,
            name=payload.name,
            version=payload.version,
            description=payload.description,
            schema_json=json.dumps(payload.model_dump(), ensure_ascii=False, default=str),
        )
        db.add(dataset)
        db.flush()
        run = run_validation_dataset(db, dataset, payload, actor_id=None)
        db.commit()
        summary = {
            "status": run.status,
            "engine_version": run.engine_version,
            "scenarios": run.scenario_count,
            "precision": run.precision,
            "recall": run.recall,
            "f1_score": run.f1_score,
            "amount_mae": float(run.amount_mae),
            "false_positives": run.false_positives,
            "false_negatives": run.false_negatives,
            "gate_passed": run.gate_passed,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        passed = run.status == "completed" and run.gate_passed
        db.delete(tenant)
        db.commit()
        return 0 if passed else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
