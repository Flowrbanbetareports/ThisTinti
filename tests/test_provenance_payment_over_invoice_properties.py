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
from app.services.payment_over_invoice_provenance import payment_over_invoice_finding_matches_current_support
from app.services.provenance import append_fact, create_origin
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
BAD_KIND = st.sampled_from(("missing", "external_unavailable", "wrong_value", "missing_locator", "wrong_pointer"))
ROLE = st.sampled_from(("invoice", "payment"))


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
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "thistinti-payment-over-invoice:" + ":".join(map(str, parts))))


class _Scenario:
    def __init__(self, db: Session, token: str):
        self.db = db
        self.token = token
        self.tenant = Tenant(id=_id(token, "tenant"), name=f"Payment provenance {token}")
        self.chain = OperationChain(id=_id(token, "chain"), tenant_id=self.tenant.id, reference_key=f"PAY-{token}")
        db.add(self.tenant)
        db.flush()
        db.add(self.chain)
        db.flush()
        self.next_index = 0

    def add(self, role: str, total: Decimal, *, kind: str = "direct") -> DocumentLine:
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
                match_reason="payment-property",
            )
        )
        self.db.flush()
        locator = {
            "locator_type": "JSON_POINTER",
            "pointer": "/lines/0/line_total",
            "engine_id": "native-json-parser",
            "engine_version": "1",
        }
        line = DocumentLine(
            id=line_id,
            tenant_id=self.tenant.id,
            document_id=document.id,
            line_no=1,
            sku=f"PAY-PROP-{idx}",
            description="Payment over invoice property item",
            unit_of_measure="EA",
            quantity=Decimal("1"),
            unit_price=total,
            price_base_quantity=Decimal("1"),
            discount_rate=Decimal("0"),
            tax_rate=Decimal("0"),
            line_total=total,
            canonical_key=f"sku:pay-prop-{idx}",
            confidence=1.0,
            raw_json=json.dumps({"_source_locators": {"line_total": locator}}, sort_keys=True, separators=(",", ":")),
        )
        self.db.add(line)
        self.db.flush()
        self._fact(document, line, total, kind)
        return line

    def _fact(self, document: Document, line: DocumentLine, total: Decimal, kind: str) -> None:
        if kind == "missing":
            return
        status = "missing" if kind == "missing_locator" else "present"
        pointer = "/lines/0/not_line_total" if kind == "wrong_pointer" else "/lines/0/line_total"
        origin = create_origin(
            self.db,
            tenant_id=self.tenant.id,
            origin_type="DOCUMENT_EVIDENCE",
            source_ref=f"sha256:{document.file_hash}",
            document_id=document.id,
            source_availability="external_unavailable" if kind == "external_unavailable" else "available",
            locator_status=status,
            locator_type="JSON_POINTER" if status == "present" else None,
            locator_json=json.dumps({"pointer": pointer}, separators=(",", ":")) if status == "present" else None,
            engine_id="native-json-parser",
            engine_version="1",
        )
        value = total + Decimal("1") if kind == "wrong_value" else total
        append_fact(
            self.db,
            tenant_id=self.tenant.id,
            fact_key=f"document_line:{line.id}:line_total",
            fact_type="document_line.line_total",
            value_json=json.dumps(str(value)),
            origin_id=origin.id,
        )

    def analyze(self) -> None:
        analyze_chain(self.db, self.chain)
        self.db.flush()

    def case(self) -> DiscrepancyCase | None:
        return self.db.scalar(
            select(DiscrepancyCase).where(
                DiscrepancyCase.tenant_id == self.tenant.id,
                DiscrepancyCase.chain_id == self.chain.id,
                DiscrepancyCase.case_type == "payment_over_invoice",
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
    invoice_total=st.integers(min_value=1, max_value=100000),
    excess=st.integers(min_value=1, max_value=100000),
)
def test_property_payment_over_invoice_complete_direct_support_binds_every_current_total(
    invoice_total: int, excess: int
) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, "property-direct")
        scenario.add("invoice", Decimal(invoice_total))
        scenario.add("payment", Decimal(invoice_total + excess))
        scenario.analyze()
        case = scenario.case()
        assert case is not None
        assert Decimal(case.amount_estimate) == Decimal(excess)
        findings = scenario.findings()
        assert len(findings) == 1
        assert payment_over_invoice_finding_matches_current_support(db, finding=findings[0]) is True
        links = list(
            db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == findings[0].id))
        )
        assert len(links) == 2


@PROPERTY_SETTINGS
@given(
    role=ROLE,
    kind=BAD_KIND,
    invoice_total=st.integers(min_value=1, max_value=10000),
    excess=st.integers(min_value=1, max_value=10000),
)
def test_property_payment_over_invoice_fails_closed_for_any_unqualified_current_total(
    role: str, kind: str, invoice_total: int, excess: int
) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, "property-hostile")
        scenario.add("invoice", Decimal(invoice_total), kind=kind if role == "invoice" else "direct")
        scenario.add("payment", Decimal(invoice_total + excess), kind=kind if role == "payment" else "direct")
        scenario.analyze()
        assert scenario.case() is not None
        assert scenario.findings() == []


class PaymentOverInvoiceStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.ctx = _isolated_db()
        self.db = self.ctx.__enter__()
        self.scenario = _Scenario(self.db, "stateful")
        self.scenario.add("invoice", Decimal("100"))
        self.scenario.add("payment", Decimal("125"))
        self.scenario.analyze()

    def teardown(self):
        self.ctx.__exit__(None, None, None)

    @rule()
    def reanalyze_is_idempotent(self):
        before = [(finding.id, finding.version) for finding in self.scenario.findings()]
        self.scenario.analyze()
        assert [(finding.id, finding.version) for finding in self.scenario.findings()] == before

    @rule()
    def temporarily_make_support_unavailable(self):
        findings = self.scenario.findings()
        assert findings
        current = findings[-1]
        fact_id = self.db.scalar(
            select(ProvenanceFindingFact.fact_id).where(ProvenanceFindingFact.finding_id == current.id)
        )
        assert fact_id is not None
        fact = self.db.get(ProvenanceFact, fact_id)
        assert fact is not None
        origin = self.db.get(ProvenanceOrigin, fact.origin_id)
        assert origin is not None
        old = origin.source_availability
        origin.source_availability = "external_unavailable"
        self.db.flush()
        assert payment_over_invoice_finding_matches_current_support(self.db, finding=current) is False
        origin.source_availability = old
        self.db.flush()

    @invariant()
    def latest_finding_is_current_when_sources_are_restored(self):
        findings = self.scenario.findings()
        assert findings
        assert payment_over_invoice_finding_matches_current_support(self.db, finding=findings[-1]) is True


TestPaymentOverInvoiceStateMachine = PaymentOverInvoiceStateMachine.TestCase
TestPaymentOverInvoiceStateMachine.settings = STATEFUL_SETTINGS
