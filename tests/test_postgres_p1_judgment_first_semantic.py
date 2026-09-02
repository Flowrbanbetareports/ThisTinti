from __future__ import annotations

import os
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import select, update

import app.legacy_cases_api as legacy_cases_api
from app.db import SessionLocal
from app.models import DiscrepancyCase, DocumentLine, ReviewDecision
from app.provenance_models import ProvenanceFinding, ProvenanceJudgment
from app.services.delivered_over_order_provenance import delivered_over_order_finding_matches_current_support
from tests.test_provenance_delivered_over_order import _upload_overdelivery


pytestmark = pytest.mark.skipif(
    not os.getenv("THISTINTI_TEST_POSTGRES_URL"),
    reason="requires a real PostgreSQL database via THISTINTI_TEST_POSTGRES_URL",
)


def _current_case_and_finding() -> tuple[str, str]:
    with SessionLocal() as db:
        case = db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "delivered_over_order"))
        assert case is not None
        finding = db.scalar(
            select(ProvenanceFinding).where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
        )
        assert finding is not None
        return case.id, finding.id


def test_real_judgment_first_serializes_mutation_and_becomes_stale_afterward(client, auth, monkeypatch):
    """A real persisted judgment commits before T2 and cannot stay exact-current after T2."""
    _order_id, delivery_id = _upload_overdelivery(
        client,
        auth,
        suffix="PG-JUDGMENT-FIRST",
        ordered="10",
        delivered="12",
    )
    case_id, finding_id = _current_case_and_finding()

    judgment_flushed = threading.Event()
    allow_judgment_commit = threading.Event()
    mutation_started = threading.Event()
    mutation_finished = threading.Event()
    judgment_errors: list[BaseException] = []
    mutation_errors: list[BaseException] = []
    judgment_status: list[int] = []

    original_record = legacy_cases_api.record_judgment_provenance

    def record_then_pause(*args, **kwargs):
        judgment = original_record(*args, **kwargs)
        assert judgment is not None
        judgment_flushed.set()
        assert allow_judgment_commit.wait(timeout=3.0)
        return judgment

    monkeypatch.setattr(legacy_cases_api, "record_judgment_provenance", record_then_pause)

    def persist_judgment() -> None:
        try:
            response = client.post(
                f"/api/cases/{case_id}/decision",
                headers=auth,
                json={
                    "decision": "confirmed",
                    "note": "Judgment-first PostgreSQL qualification evidence.",
                },
            )
            judgment_status.append(response.status_code)
            assert response.status_code == 200, response.text
        except BaseException as exc:
            judgment_errors.append(exc)

    def mutate_delivery_support() -> None:
        try:
            with SessionLocal() as mutator, mutator.begin():
                mutator.connection().exec_driver_sql("SET LOCAL lock_timeout = '3s'")
                mutation_started.set()
                mutator.execute(
                    update(DocumentLine)
                    .where(
                        DocumentLine.document_id == delivery_id,
                        DocumentLine.line_no == 1,
                    )
                    .values(quantity=Decimal("8"))
                )
        except BaseException as exc:
            mutation_errors.append(exc)
        finally:
            mutation_finished.set()

    judgment_worker = threading.Thread(target=persist_judgment, daemon=True)
    judgment_worker.start()
    assert judgment_flushed.wait(timeout=2.0)

    mutation_worker = threading.Thread(target=mutate_delivery_support, daemon=True)
    mutation_worker.start()
    assert mutation_started.wait(timeout=1.0)
    time.sleep(0.35)
    assert not mutation_finished.is_set(), "support mutation must block behind the judgment transaction"

    allow_judgment_commit.set()
    judgment_worker.join(timeout=3.0)
    mutation_worker.join(timeout=3.0)

    assert not judgment_worker.is_alive()
    assert not mutation_worker.is_alive()
    assert not judgment_errors
    assert not mutation_errors
    assert judgment_status == [200]
    assert mutation_finished.is_set()

    with SessionLocal() as db:
        decision = db.scalar(select(ReviewDecision).where(ReviewDecision.case_id == case_id))
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        finding = db.get(ProvenanceFinding, finding_id)
        persisted_quantity = db.scalar(
            select(DocumentLine.quantity).where(
                DocumentLine.document_id == delivery_id,
                DocumentLine.line_no == 1,
            )
        )

        assert decision is not None
        assert judgment is not None
        assert judgment.review_decision_id == decision.id
        assert Decimal(persisted_quantity) == Decimal("8")
        assert finding is not None
        assert not delivered_over_order_finding_matches_current_support(db, finding=finding)


def test_conflicting_real_judgments_serialize_into_deterministic_history(client, auth, monkeypatch):
    """Two incompatible real decisions must serialize into one unambiguous state history."""
    _upload_overdelivery(
        client,
        auth,
        suffix="PG-CONFLICTING-JUDGMENTS",
        ordered="10",
        delivered="12",
    )
    case_id, finding_id = _current_case_and_finding()

    first_judgment_flushed = threading.Event()
    allow_first_commit = threading.Event()
    second_started = threading.Event()
    second_finished = threading.Event()
    worker_errors: list[BaseException] = []
    outcomes: dict[str, int] = {}

    original_record = legacy_cases_api.record_judgment_provenance

    def record_then_pause_first(*args, **kwargs):
        judgment = original_record(*args, **kwargs)
        assert judgment is not None
        review_decision = kwargs["review_decision"]
        if review_decision.decision == "confirmed":
            first_judgment_flushed.set()
            assert allow_first_commit.wait(timeout=3.0)
        return judgment

    monkeypatch.setattr(legacy_cases_api, "record_judgment_provenance", record_then_pause_first)

    def decide(name: str, decision: str, note: str) -> None:
        try:
            if name == "second":
                second_started.set()
            response = client.post(
                f"/api/cases/{case_id}/decision",
                headers=auth,
                json={"decision": decision, "note": note},
            )
            outcomes[name] = response.status_code
            assert response.status_code == 200, response.text
        except BaseException as exc:
            worker_errors.append(exc)
        finally:
            if name == "second":
                second_finished.set()

    first = threading.Thread(
        target=decide,
        args=("first", "confirmed", "First conflicting PostgreSQL judgment."),
        daemon=True,
    )
    first.start()
    assert first_judgment_flushed.wait(timeout=2.0)

    second = threading.Thread(
        target=decide,
        args=("second", "dismissed", "Second conflicting PostgreSQL judgment."),
        daemon=True,
    )
    second.start()
    assert second_started.wait(timeout=1.0)
    time.sleep(0.35)
    assert not second_finished.is_set(), "the second judgment must block behind the first transaction"

    allow_first_commit.set()
    first.join(timeout=3.0)
    second.join(timeout=3.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert not worker_errors
    assert outcomes == {"first": 200, "second": 200}

    with SessionLocal() as db:
        case = db.get(DiscrepancyCase, case_id)
        assert case is not None
        assert case.status == "dismissed"

        decisions = list(db.scalars(select(ReviewDecision).where(ReviewDecision.case_id == case_id)))
        judgments = list(
            db.scalars(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        )
        assert len(decisions) == 2
        assert len(judgments) == 2
        assert {decision.decision for decision in decisions} == {"confirmed", "dismissed"}
        assert {judgment.review_decision_id for judgment in judgments} == {decision.id for decision in decisions}

        by_decision = {judgment.decision: judgment for judgment in judgments}
        assert by_decision["confirmed"].previous_state == "needs_review"
        assert by_decision["dismissed"].previous_state == "confirmed"
