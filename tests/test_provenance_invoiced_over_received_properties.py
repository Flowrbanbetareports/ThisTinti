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
from app.services.invoiced_over_received_provenance import invoiced_over_received_finding_matches_current_support
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
FIELD = st.sampled_from(
    (
        "reference_quantity",
        "reference_uom",
        "invoice_quantity",
        "invoice_uom",
        "invoice_unit_price",
        "invoice_price_base_quantity",
    )
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
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "thistinti-invoiced-over-received:" + ":".join(map(str, parts))))


class _Scenario:
    def __init__(self, db: Session, token: str):
        self.db = db
        self.token = token
        self.tenant = Tenant(id=_id(token, "tenant"), name=f"Invoice provenance {token}")
        self.chain = OperationChain(id=_id(token, "chain"), tenant_id=self.tenant.id, reference_key=f"INV-{token}")
        db.add(self.tenant)
        db.flush()
        db.add(self.chain)
        db.flush()
        self.next_index = 0

    def add(
        self,
        role: str,
        quantity: Decimal,
        *,
        unit_price: Decimal = Decimal("5"),
        price_base: Decimal = Decimal("1"),
        kinds: dict[str, str] | None = None,
    ) -> DocumentLine:
        kinds = kinds or {}
        idx = self.next_index
        self.next_index += 1
        document_id = _id(self.token, "document", idx)
        line_id = _id(self.token, "line", idx)
        digest = hashlib.sha256(f"{self.token}:{idx}:{role}:{quantity}:{unit_price}:{price_base}".encode()).hexdigest()
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
                match_reason="invoice-property",
            )
        )
        self.db.flush()
        locators = {
            field: {
                "locator_type": "JSON_POINTER",
                "pointer": f"/lines/0/{field}",
                "engine_id": "native-json-parser",
                "engine_version": "1",
            }
            for field in ("quantity", "unit_of_measure", "unit_price", "price_base_quantity")
        }
        line = DocumentLine(
            id=line_id,
            tenant_id=self.tenant.id,
            document_id=document.id,
            line_no=1,
            sku="INV-PROP-ITEM",
            description="Invoiced over received property item",
            unit_of_measure="EA",
            quantity=quantity,
            unit_price=unit_price,
            price_base_quantity=price_base,
            discount_rate=Decimal("0"),
            tax_rate=Decimal("0"),
            line_total=quantity * unit_price / price_base,
            canonical_key="sku:inv-prop-item",
            confidence=1.0,
            raw_json=json.dumps({"_source_locators": locators}, sort_keys=True, separators=(",", ":")),
        )
        self.db.add(line)
        self.db.flush()
        required = (
            ("quantity", "unit_of_measure", "unit_price", "price_base_quantity")
            if role == "invoice"
            else ("quantity", "unit_of_measure")
        )
        values = {
            "quantity": quantity,
            "unit_of_measure": "EA",
            "unit_price": unit_price,
            "price_base_quantity": price_base,
        }
        for field in required:
            self._fact(document, line, field, values[field], kinds.get(field, "direct"))
        return line

    def _fact(self, document: Document, line: DocumentLine, field: str, value: object, kind: str) -> None:
        if kind == "missing":
            return
        status = "missing" if kind == "missing_locator" else "present"
        pointer = f"/lines/0/not_{field}" if kind == "wrong_pointer" else f"/lines/0/{field}"
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
        fact_value: object
        if kind == "wrong_value":
            fact_value = "BROKEN" if field == "unit_of_measure" else str(Decimal(str(value)) + Decimal("1"))
        else:
            fact_value = value if field == "unit_of_measure" else str(value)
        fact_type = {
            "quantity": "document_line.quantity",
            "unit_of_measure": "document_line.unit_of_measure",
            "unit_price": "document_line.unit_price",
            "price_base_quantity": "document_line.price_base_quantity",
        }[field]
        append_fact(
            self.db,
            tenant_id=self.tenant.id,
            fact_key=f"document_line:{line.id}:{field}",
            fact_type=fact_type,
            value_json=json.dumps(fact_value),
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
                DiscrepancyCase.case_type == "invoiced_over_received",
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
    received=st.integers(min_value=1, max_value=10000),
    excess=st.integers(min_value=1, max_value=10000),
    unit_price=st.integers(min_value=1, max_value=10000),
    price_base=st.integers(min_value=1, max_value=100),
)
def test_property_invoiced_over_received_complete_direct_support_binds_all_inputs(
    received: int, excess: int, unit_price: int, price_base: int
) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, "property-direct")
        scenario.add("delivery", Decimal(received))
        scenario.add(
            "invoice", Decimal(received + excess), unit_price=Decimal(unit_price), price_base=Decimal(price_base)
        )
        scenario.analyze()
        case = scenario.case()
        assert case is not None
        findings = scenario.findings()
        assert len(findings) == 1
        assert invoiced_over_received_finding_matches_current_support(db, finding=findings[0]) is True
        links = list(
            db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == findings[0].id))
        )
        assert len(links) == 6


@PROPERTY_SETTINGS
@given(
    field=FIELD,
    kind=BAD_KIND,
    received=st.integers(min_value=1, max_value=500),
    excess=st.integers(min_value=1, max_value=500),
)
def test_property_invoiced_over_received_fails_closed_for_any_unqualified_required_input(
    field: str, kind: str, received: int, excess: int
) -> None:
    target, source = field.split("_", 1)
    source = "unit_of_measure" if source == "uom" else source
    if source == "price_base_quantity":
        source = "price_base_quantity"
    reference_kinds: dict[str, str] = {}
    invoice_kinds: dict[str, str] = {}
    (reference_kinds if target == "reference" else invoice_kinds)[source] = kind
    with _isolated_db() as db:
        scenario = _Scenario(db, "property-hostile")
        scenario.add("delivery", Decimal(received), kinds=reference_kinds)
        scenario.add("invoice", Decimal(received + excess), kinds=invoice_kinds)
        scenario.analyze()
        assert scenario.case() is not None
        assert scenario.findings() == []


class InvoicedOverReceivedStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.ctx = _isolated_db()
        self.db = self.ctx.__enter__()
        self.scenario = _Scenario(self.db, "stateful")
        self.scenario.add("delivery", Decimal("10"))
        self.scenario.add("invoice", Decimal("12"))
        self.scenario.analyze()

    def teardown(self):
        self.ctx.__exit__(None, None, None)

    @rule()
    def reanalyze_is_idempotent(self):
        before = [(f.id, f.version) for f in self.scenario.findings()]
        self.scenario.analyze()
        assert [(f.id, f.version) for f in self.scenario.findings()] == before

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
        assert invoiced_over_received_finding_matches_current_support(self.db, finding=current) is False
        origin.source_availability = old
        self.db.flush()

    @invariant()
    def latest_finding_is_current_when_sources_are_restored(self):
        findings = self.scenario.findings()
        assert findings
        assert invoiced_over_received_finding_matches_current_support(self.db, finding=findings[-1]) is True


TestInvoicedOverReceivedStateMachine = InvoicedOverReceivedStateMachine.TestCase
TestInvoicedOverReceivedStateMachine.settings = STATEFUL_SETTINGS
