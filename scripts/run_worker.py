#!/usr/bin/env python3
from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import ProcessingJob  # noqa: E402
from app.services.jobs import claim_next_job, execute_job, run_maintenance, touch_worker  # noqa: E402


def run_once(worker_id: str) -> bool:
    with SessionLocal() as db:
        touch_worker(db, worker_id)
        job = claim_next_job(db, worker_id)
        if not job:
            db.commit()
            return False
        job_id = job.id
        db.commit()
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if not job or job.status != "running" or job.locked_by != worker_id:
            return False
        execute_job(db, job)
        db.commit()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="ThisTinti persistent processing worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-worker")
    args = parser.parse_args()
    worker_id = args.worker_id[:120]
    last_maintenance = 0.0
    while True:
        processed = run_once(worker_id)
        now = time.monotonic()
        if now - last_maintenance >= 60:
            with SessionLocal() as db:
                touch_worker(db, worker_id)
                run_maintenance(db)
                db.commit()
            last_maintenance = now
        if args.once:
            return 0
        if not processed:
            time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
