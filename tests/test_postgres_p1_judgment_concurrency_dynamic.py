from __future__ import annotations

import os
import threading
import time

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.db import Base
from app.legacy_cases_api import (
    _case_query,
    _case_support_identity_is_stable,
    _locked_case_query,
)
from app.models import (
    ChainDocument,
    DiscrepancyCase,
    Document,
    DocumentLine,
    OperationChain,
    Supplier,
    Tenant,
)
from app.services.judgment_provenance import lock_p1_support_for_update


pytestmark = pytest.mark.skipif(
    not os.getenv("THISTINTI_TEST_POSTGRES_URL"),
    reason="requires a real PostgreSQL database via THISTINTI_TEST_POSTGRES_URL",
)


@pytest.fixture()
def postgres_engine():
    engine = create_engine(os.environ["THISTINTI_TEST_POSTGRES_URL"], future=True)
    tables = [
        Tenant.__table__,
        Supplier.__table__,
        Document.__table__,
        DocumentLine.__table__,
        OperationChain.__table__,
        ChainDocument.__table__,
        DiscrepancyCase.__table__,
    ]
    Base.metadata.drop_all(engine, tables=tables, checkfirst=True)
    Base.metadata.create_all(engine, tables=tables, checkfirst=True)

    with Session(engine) as db, db.begin():
        db.add(Tenant(id="tenant-1", name="Concurrency evidence tenant"))
        db.flush()
        db.add(
            Document(
                id="doc-1",
                tenant_id="tenant-1",
                document_type="order",
                source_filename="order.json",
                storage_path="/qualification/order.json",
                file_hash="a" * 64,
                parse_status="parsed",
            )
        )
        db.flush()
        db.add(
            DocumentLine(
                id="line-1",
                tenant_id="tenant-1",
                document_id="doc-1",
                line_no=1,
                description="before",
            )
        )
        db.add(OperationChain(id="chain-1", tenant_id="tenant-1", order_document_id="doc-1"))
        db.add(OperationChain(id="chain-2", tenant_id="tenant-1"))
        db.flush()
        db.add(
            ChainDocument(
                id="link-1",
                tenant_id="tenant-1",
                chain_id="chain-1",
                document_id="doc-1",
                role="order",
                sequence_no=1,
            )
        )
        db.add(
            DiscrepancyCase(
                id="case-1",
                tenant_id="tenant-1",
                chain_id="chain-1",
                fingerprint="f" * 64,
                case_type="delivered_over_order",
                severity="high",
                status="needs_review",
                title="Concurrency qualification case",
                explanation="Synthetic qualification-only case.",
            )
        )

    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine, tables=tables, checkfirst=True)
        engine.dispose()


def test_judgment_first_blocks_then_serializes_membership_mutation(postgres_engine):
    """A support mutation cannot pass the P1 support locks before judgment commits."""
    mutation_started = threading.Event()
    mutation_finished = threading.Event()
    mutation_errors: list[BaseException] = []

    judgment = Session(postgres_engine)
    judgment.begin()
    try:
        assert lock_p1_support_for_update(judgment, tenant_id="tenant-1", chain_id="chain-1")
        assert judgment.scalar(_locked_case_query(case_id="case-1", tenant_id="tenant-1")) is not None

        def mutate_membership() -> None:
            try:
                with Session(postgres_engine) as mutator, mutator.begin():
                    mutator.connection().exec_driver_sql("SET LOCAL lock_timeout = '3s'")
                    mutation_started.set()
                    mutator.execute(
                        update(ChainDocument)
                        .where(
                            ChainDocument.id == "link-1",
                            ChainDocument.tenant_id == "tenant-1",
                        )
                        .values(sequence_no=2)
                    )
            except BaseException as exc:
                mutation_errors.append(exc)
            finally:
                mutation_finished.set()

        worker = threading.Thread(target=mutate_membership, daemon=True)
        worker.start()
        assert mutation_started.wait(timeout=1.0)
        time.sleep(0.35)
        assert not mutation_finished.is_set()

        judgment.commit()
        worker.join(timeout=2.0)
        assert mutation_finished.is_set()
        assert not mutation_errors
    finally:
        if judgment.in_transaction():
            judgment.rollback()
        judgment.close()

    with Session(postgres_engine) as db:
        sequence_no = db.scalar(select(ChainDocument.sequence_no).where(ChainDocument.id == "link-1"))
        assert sequence_no == 2


def test_mutation_first_is_visible_to_the_subsequent_support_lock(postgres_engine):
    """A committed support mutation is not hidden by a later judgment-side lock."""
    with Session(postgres_engine) as mutator, mutator.begin():
        mutator.execute(
            update(DocumentLine)
            .where(DocumentLine.id == "line-1", DocumentLine.tenant_id == "tenant-1")
            .values(description="mutated-before-judgment")
        )

    with Session(postgres_engine) as judgment, judgment.begin():
        assert lock_p1_support_for_update(judgment, tenant_id="tenant-1", chain_id="chain-1")
        description = judgment.scalar(select(DocumentLine.description).where(DocumentLine.id == "line-1"))
        assert description == "mutated-before-judgment"


def test_initial_case_lookup_chain_drift_refreshes_and_fails_closed(postgres_engine):
    """A case moved after the unlocked lookup cannot be judged under the old chain lock."""
    judgment = Session(postgres_engine)
    judgment.begin()
    try:
        initial_case = judgment.scalar(_case_query(case_id="case-1", tenant_id="tenant-1"))
        assert initial_case is not None
        observed_case_type = initial_case.case_type
        observed_chain_id = initial_case.chain_id
        assert observed_chain_id == "chain-1"

        with Session(postgres_engine) as mutator, mutator.begin():
            mutator.execute(
                update(DiscrepancyCase)
                .where(
                    DiscrepancyCase.id == "case-1",
                    DiscrepancyCase.tenant_id == "tenant-1",
                )
                .values(chain_id="chain-2")
            )

        assert lock_p1_support_for_update(
            judgment,
            tenant_id="tenant-1",
            chain_id=observed_chain_id,
        )
        locked_case = judgment.scalar(_locked_case_query(case_id="case-1", tenant_id="tenant-1"))
        assert locked_case is initial_case
        assert locked_case.chain_id == "chain-2"
        assert not _case_support_identity_is_stable(
            locked_case,
            observed_case_type=observed_case_type,
            observed_chain_id=observed_chain_id,
        )
    finally:
        judgment.rollback()
        judgment.close()


def test_initial_case_lookup_rule_drift_refreshes_and_fails_closed(postgres_engine):
    """A concurrent P1 rule-identity change cannot inherit the original support lock."""
    judgment = Session(postgres_engine)
    judgment.begin()
    try:
        initial_case = judgment.scalar(_case_query(case_id="case-1", tenant_id="tenant-1"))
        assert initial_case is not None
        observed_case_type = initial_case.case_type
        observed_chain_id = initial_case.chain_id
        assert observed_case_type == "delivered_over_order"

        with Session(postgres_engine) as mutator, mutator.begin():
            mutator.execute(
                update(DiscrepancyCase)
                .where(
                    DiscrepancyCase.id == "case-1",
                    DiscrepancyCase.tenant_id == "tenant-1",
                )
                .values(case_type="currency_mismatch")
            )

        assert lock_p1_support_for_update(
            judgment,
            tenant_id="tenant-1",
            chain_id=observed_chain_id,
        )
        locked_case = judgment.scalar(_locked_case_query(case_id="case-1", tenant_id="tenant-1"))
        assert locked_case is initial_case
        assert locked_case.case_type == "currency_mismatch"
        assert not _case_support_identity_is_stable(
            locked_case,
            observed_case_type=observed_case_type,
            observed_chain_id=observed_chain_id,
        )
    finally:
        judgment.rollback()
        judgment.close()
