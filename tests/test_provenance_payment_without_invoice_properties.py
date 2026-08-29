from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from decimal import Decimal

from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import ChainDocument, DiscrepancyCase, Document, DocumentLine, OperationChain, Tenant
from app.provenance_models import ProvenanceFact, ProvenanceFinding, ProvenanceFindingFact, ProvenanceOrigin
from app.services.payment_without_invoice_provenance import payment_without_invoice_finding_matches_current_support
from app.services.rules import analyze_chain

PROPERTY_SETTINGS = settings(
    max_examples=1000 if os.environ.get("THISTINTI_HYPOTHESIS_PROFILE") == "deep" else 150,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
STATEFUL_SETTINGS = settings(
    max_examples=200 if os.environ.get("THISTINTI_HYPOTHESIS_PROFILE") == "deep" else 60,
    stateful_step_count=75 if os.environ.get("THISTINTI_HYPOTHESIS_PROFILE") == "deep" else 25,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)


@contextmanager
def _isolated_db():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, expire_on_commit=False)
    try:
        yield db
    finally:
        db.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def _id(*parts: object) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "thistinti-payment-without-invoice:" + ":".join(map(str, parts))))


class _Scenario:
    def __init__(self, db: Session, token: str):
        self.db = db
        self.token = token
        self.tenant = Tenant(id=_id(token, "tenant"), name=f"Absence provenance {token}")
        self.chain = OperationChain(id=_id(token, "chain"), tenant_id=self.tenant.id, reference_key=f"ABS-{token}")
        db.add(self.tenant)
        db.flush()
        db.add(self.chain)
        db.flush()
        self.next_index = 0

    def add(self, role: str, total: Decimal, *, numeric_available: bool = True) -> str:
        idx = self.next_index
        self.next_index += 1
        document_id = _id(self.token, "document", idx)
        line_id = _id(self.token, "line", idx)
        digest = hashlib.sha256(f"{self.token}:{idx}:{role}:{total}".encode()).hexdigest()
        document = Document(
            id=document_id,
            tenant_id=self.tenant.id,
            document_type=role,
            number=f"{role.upper()}-{self.token}-{idx}",
            currency="EUR",
            source_filename=f"{role}-{idx}.json",
            storage_path=f"/tmp/{document_id}.json",
            file_hash=digest,
            parse_status="parsed",
            confidence=1.0,
        )
        self.db.add(document)
        self.db.flush()
        self.db.add(
            ChainDocument(
                tenant_id=self.tenant.id,
                chain_id=self.chain.id,
                document_id=document.id,
                role=role,
                sequence_no=idx + 1,
                match_confidence=1.0,
                match_reason="absence-property",
            )
        )
        primary_field = f"{role}_document_id"
        if getattr(self.chain, primary_field) is None:
            setattr(self.chain, primary_field, document.id)
        raw = {
            "numeric_provenance": {
                "line_total": "source" if numeric_available else "missing",
            }
        }
        self.db.add(
            DocumentLine(
                id=line_id,
                tenant_id=self.tenant.id,
                document_id=document.id,
                line_no=1,
                sku=f"ABS-{idx}",
                description="Payment without invoice property item",
                unit_of_measure="EA",
                quantity=Decimal("1"),
                unit_price=total,
                price_base_quantity=Decimal("1"),
                discount_rate=Decimal("0"),
                tax_rate=Decimal("0"),
                line_total=total,
                canonical_key=f"sku:absence-{idx}",
                confidence=1.0,
                raw_json=json.dumps(raw, sort_keys=True, separators=(",", ":")),
            )
        )
        self.db.flush()
        return document.id

    def analyze(self) -> None:
        analyze_chain(self.db, self.chain)
        self.db.flush()

    def case(self) -> DiscrepancyCase | None:
        return self.db.scalar(
            select(DiscrepancyCase).where(
                DiscrepancyCase.tenant_id == self.tenant.id,
                DiscrepancyCase.chain_id == self.chain.id,
                DiscrepancyCase.case_type == "payment_without_invoice",
            )
        )

    def findings(self) -> list[ProvenanceFinding]:
        case = self.case()
        if case is None:
            return []
        return list(
            self.db.scalars(
                select(ProvenanceFinding)
                .where(ProvenanceFinding.case_id == case.id)
                .order_by(ProvenanceFinding.version)
            )
        )


@PROPERTY_SETTINGS
@given(
    totals=st.lists(st.integers(min_value=0, max_value=100000), min_size=1, max_size=5),
)
def test_property_payment_without_invoice_snapshot_binds_exact_current_payment_membership(totals: list[int]) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, "property-membership")
        for total in totals:
            scenario.add("payment", Decimal(total))
        scenario.analyze()
        case = scenario.case()
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal(sum(totals))
        findings = scenario.findings()
        assert len(findings) == 1
        assert payment_without_invoice_finding_matches_current_support(db, finding=findings[0]) is True
        link = db.scalar(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == findings[0].id))
        assert link is not None
        fact = db.get(ProvenanceFact, link.fact_id)
        assert fact is not None
        snapshot = json.loads(fact.value_json)
        assert snapshot["invoice_document_ids"] == []
        assert len(snapshot["payment_document_ids"]) == len(totals)
        assert snapshot["matcher"]["version"] == "1"
        assert snapshot["rule"]["version"] == "1"


@PROPERTY_SETTINGS
@given(
    totals=st.lists(st.integers(min_value=1, max_value=10000), min_size=1, max_size=4),
    missing_index=st.integers(min_value=0, max_value=3),
)
def test_property_payment_without_invoice_numeric_unknown_does_not_expand_absence_claim(
    totals: list[int], missing_index: int
) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, "property-unknown")
        chosen = missing_index % len(totals)
        for index, total in enumerate(totals):
            scenario.add("payment", Decimal(total), numeric_available=index != chosen)
        scenario.analyze()
        case = scenario.case()
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal("0.00")
        finding = scenario.findings()[0]
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True
        fact_id = db.scalar(select(ProvenanceFindingFact.fact_id).where(ProvenanceFindingFact.finding_id == finding.id))
        assert fact_id is not None
        fact = db.get(ProvenanceFact, fact_id)
        assert fact is not None
        snapshot = json.loads(fact.value_json)
        assert snapshot["payment_total"]["status"] == "numeric_inputs_unavailable"
        assert "global" in snapshot["claim_boundary"]


@PROPERTY_SETTINGS
@given(
    payment_total=st.integers(min_value=0, max_value=100000),
    invoice_total=st.integers(min_value=0, max_value=100000),
)
def test_property_any_invoice_membership_invalidates_payment_without_invoice_support(
    payment_total: int, invoice_total: int
) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, "property-invoice-arrival")
        scenario.add("payment", Decimal(payment_total))
        scenario.analyze()
        finding = scenario.findings()[0]
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is True
        scenario.add("invoice", Decimal(invoice_total))
        scenario.analyze()
        assert payment_without_invoice_finding_matches_current_support(db, finding=finding) is False
        case = scenario.case()
        assert case is not None
        assert case.status == "superseded"


class PaymentWithoutInvoiceStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.ctx = _isolated_db()
        self.db = self.ctx.__enter__()
        self.scenario = _Scenario(self.db, "stateful")
        self.scenario.add("payment", Decimal("100"))
        self.scenario.analyze()

    def teardown(self):
        self.ctx.__exit__(None, None, None)

    @rule()
    def reanalyze_is_idempotent(self):
        before = [(finding.id, finding.version) for finding in self.scenario.findings()]
        self.scenario.analyze()
        assert [(finding.id, finding.version) for finding in self.scenario.findings()] == before

    @rule(total=st.integers(min_value=0, max_value=10000))
    def add_payment_versions_exact_snapshot(self, total: int):
        before = self.scenario.findings()
        previous = before[-1]
        self.scenario.add("payment", Decimal(total))
        self.scenario.analyze()
        after = self.scenario.findings()
        assert len(after) == len(before) + 1
        assert after[-1].supersedes_finding_id == previous.id
        assert payment_without_invoice_finding_matches_current_support(self.db, finding=previous) is False
        assert payment_without_invoice_finding_matches_current_support(self.db, finding=after[-1]) is True

    @rule()
    def temporarily_stale_matcher_metadata_fails_closed(self):
        current = self.scenario.findings()[-1]
        fact_id = self.db.scalar(
            select(ProvenanceFindingFact.fact_id).where(ProvenanceFindingFact.finding_id == current.id)
        )
        assert fact_id is not None
        fact = self.db.get(ProvenanceFact, fact_id)
        assert fact is not None
        origin = self.db.get(ProvenanceOrigin, fact.origin_id)
        assert origin is not None
        old = origin.engine_version
        origin.engine_version = "stale"
        self.db.flush()
        assert payment_without_invoice_finding_matches_current_support(self.db, finding=current) is False
        origin.engine_version = old
        self.db.flush()

    @invariant()
    def latest_finding_matches_restored_current_snapshot(self):
        findings = self.scenario.findings()
        assert findings
        assert payment_without_invoice_finding_matches_current_support(self.db, finding=findings[-1]) is True


TestPaymentWithoutInvoiceStateMachine = PaymentWithoutInvoiceStateMachine.TestCase
TestPaymentWithoutInvoiceStateMachine.settings = STATEFUL_SETTINGS
