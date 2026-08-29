from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from decimal import Decimal

from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import (
    ChainDocument,
    DiscrepancyCase,
    Document,
    DocumentLine,
    OperationChain,
    ReviewDecision,
    Tenant,
    User,
    utcnow,
)
from app.provenance_models import (
    ProvenanceFact,
    ProvenanceFinding,
    ProvenanceFindingFact,
    ProvenanceJudgment,
    ProvenanceOrigin,
)
from app.services.delivered_over_order_provenance import (
    delivered_over_order_finding_matches_current_support,
)
from app.services.judgment_provenance import record_judgment_provenance
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
PROVENANCE_KIND_STRATEGY = st.sampled_from(
    (
        "direct",
        "missing",
        "external_unavailable",
        "human",
        "wrong_value",
        "missing_locator",
        "wrong_pointer",
    )
)
FIELD_STRATEGY = st.sampled_from(
    (
        "order_quantity",
        "order_uom",
        "order_unit_price",
        "order_price_base_quantity",
        "delivery_quantity",
        "delivery_uom",
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


def _stable_id(*parts: object) -> str:
    key = ":".join(str(part) for part in parts)
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"thistinti-delivered-over-order-provenance:{key}",
        )
    )


def _finding_versions(
    db: Session,
    case: DiscrepancyCase,
) -> list[ProvenanceFinding]:
    return list(
        db.scalars(
            select(ProvenanceFinding)
            .where(
                ProvenanceFinding.tenant_id == case.tenant_id,
                ProvenanceFinding.case_id == case.id,
            )
            .order_by(ProvenanceFinding.version)
        )
    )


class _DeliveredScenario:
    def __init__(self, db: Session, *, token: str):
        self.db = db
        self.token = token
        self.tenant = Tenant(
            id=_stable_id(token, "tenant"),
            name=f"Delivered provenance {token}",
        )
        self.user = User(
            id=_stable_id(token, "user"),
            tenant_id=self.tenant.id,
            email=f"{_stable_id(token, 'email')}@example.com",
            password_hash="delivered-property-test-only",
            role="reviewer",
        )
        self.chain = OperationChain(
            id=_stable_id(token, "chain"),
            tenant_id=self.tenant.id,
            reference_key=f"DEL-{token}",
        )
        db.add(self.tenant)
        db.flush()
        db.add(self.user)
        db.flush()
        db.add(self.chain)
        db.flush()
        self.document_kinds: dict[int, dict[str, str]] = {}
        self.next_sequence = 1

    def add_line_document(
        self,
        logical_index: int,
        *,
        role: str,
        quantity: Decimal,
        unit_price: Decimal = Decimal("5"),
        price_base_quantity: Decimal = Decimal("1"),
        uom: str = "EA",
        kinds: dict[str, str] | None = None,
    ) -> DocumentLine:
        kinds = dict(kinds or {})
        document_id = _stable_id(self.token, "document", logical_index)
        line_id = _stable_id(self.token, "line", logical_index)
        digest = hashlib.sha256(
            (f"{self.token}:{logical_index}:{role}:{quantity}:{unit_price}:{price_base_quantity}:{uom}").encode()
        ).hexdigest()
        document = Document(
            id=document_id,
            tenant_id=self.tenant.id,
            document_type=role,
            number=f"{role.upper()}-DEL-PROP-{logical_index}",
            currency="EUR",
            source_filename=f"delivered-{logical_index}.json",
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
                sequence_no=self.next_sequence,
                match_confidence=1.0,
                match_reason="delivered-property-test",
            )
        )
        self.next_sequence += 1
        self.db.flush()

        fields = {
            "quantity": quantity,
            "unit_of_measure": uom,
            "unit_price": unit_price,
            "price_base_quantity": price_base_quantity,
        }
        required = (
            (
                "quantity",
                "unit_of_measure",
                "unit_price",
                "price_base_quantity",
            )
            if role == "order"
            else ("quantity", "unit_of_measure")
        )
        locators = {
            field: {
                "locator_type": "JSON_POINTER",
                "pointer": f"/lines/0/{field}",
                "engine_id": "native-json-parser",
                "engine_version": "1",
            }
            for field in fields
        }
        line = DocumentLine(
            id=line_id,
            tenant_id=self.tenant.id,
            document_id=document.id,
            line_no=1,
            sku="DEL-PROP-ITEM",
            description="Delivered over order property item",
            unit_of_measure=uom,
            quantity=quantity,
            unit_price=unit_price,
            price_base_quantity=price_base_quantity,
            discount_rate=Decimal("0"),
            tax_rate=Decimal("0"),
            line_total=quantity * unit_price / price_base_quantity,
            canonical_key="sku:del-prop-item",
            confidence=1.0,
            raw_json=json.dumps(
                {"_source_locators": locators},
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        self.db.add(line)
        self.db.flush()

        self.document_kinds[logical_index] = {}
        for field in required:
            kind = kinds.get(field, "direct")
            self.document_kinds[logical_index][field] = kind
            self._attach_fact(
                document=document,
                line=line,
                field=field,
                value=fields[field],
                kind=kind,
            )
        return line

    def _attach_fact(
        self,
        *,
        document: Document,
        line: DocumentLine,
        field: str,
        value: object,
        kind: str,
    ) -> None:
        if kind == "missing":
            return
        if kind in {
            "direct",
            "external_unavailable",
            "wrong_value",
            "missing_locator",
            "wrong_pointer",
        }:
            locator_status = "missing" if kind == "missing_locator" else "present"
            pointer = f"/lines/0/not_{field}" if kind == "wrong_pointer" else f"/lines/0/{field}"
            origin = create_origin(
                self.db,
                tenant_id=self.tenant.id,
                origin_type="DOCUMENT_EVIDENCE",
                source_ref=f"sha256:{document.file_hash}",
                document_id=document.id,
                source_availability=("external_unavailable" if kind == "external_unavailable" else "available"),
                locator_status=locator_status,
                locator_type="JSON_POINTER" if locator_status == "present" else None,
                locator_json=(
                    json.dumps({"pointer": pointer}, separators=(",", ":")) if locator_status == "present" else None
                ),
                engine_id="native-json-parser",
                engine_version="1",
            )
        elif kind == "human":
            origin = create_origin(
                self.db,
                tenant_id=self.tenant.id,
                origin_type="HUMAN_ASSERTION",
                actor_ref=f"user:{self.user.id}",
                actor_user_id=self.user.id,
                reason="Hostile manual delivered-over-order input.",
                asserted_at=utcnow(),
            )
        else:
            raise AssertionError(f"unsupported provenance kind: {kind}")

        if kind == "wrong_value":
            fact_value: object = "BROKEN" if field == "unit_of_measure" else str(Decimal(str(value)) + Decimal("1"))
        else:
            fact_value = str(value) if field != "unit_of_measure" else value
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
                DiscrepancyCase.case_type == "delivered_over_order",
            )
        )

    def findings(self) -> list[ProvenanceFinding]:
        case = self.case()
        return [] if case is None else _finding_versions(self.db, case)

    def all_support_is_direct(self) -> bool:
        return all(kind == "direct" for fields in self.document_kinds.values() for kind in fields.values())

    def review(self, *, note: str) -> ProvenanceJudgment | None:
        case = self.case()
        assert case is not None
        decision = ReviewDecision(
            tenant_id=self.tenant.id,
            case_id=case.id,
            user_id=self.user.id,
            decision="confirmed",
            note=note,
        )
        self.db.add(decision)
        self.db.flush()
        return record_judgment_provenance(
            self.db,
            tenant_id=self.tenant.id,
            case_id=case.id,
            review_decision=decision,
            reviewer_ref=f"user:{self.user.id}",
            reviewer_user_id=self.user.id,
            previous_state="open",
        )


@PROPERTY_SETTINGS
@given(
    ordered=st.integers(min_value=1, max_value=10_000),
    excess=st.integers(min_value=1, max_value=10_000),
    unit_price=st.integers(min_value=1, max_value=10_000),
    price_base=st.integers(min_value=1, max_value=100),
)
def test_property_delivered_over_order_complete_direct_support_binds_every_engine_input(
    ordered: int,
    excess: int,
    unit_price: int,
    price_base: int,
) -> None:
    with _isolated_db() as db:
        scenario = _DeliveredScenario(db, token="property-direct")
        scenario.add_line_document(
            0,
            role="order",
            quantity=Decimal(ordered),
            unit_price=Decimal(unit_price),
            price_base_quantity=Decimal(price_base),
        )
        scenario.add_line_document(
            1,
            role="delivery",
            quantity=Decimal(ordered + excess),
        )
        scenario.analyze()

        case = scenario.case()
        assert case is not None
        findings = scenario.findings()
        assert len(findings) == 1
        finding = findings[0]
        assert (
            delivered_over_order_finding_matches_current_support(
                db,
                finding=finding,
            )
            is True
        )
        links = list(db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == finding.id)))
        assert len(links) == 6
        facts = [db.get(ProvenanceFact, link.fact_id) for link in links]
        assert all(fact is not None for fact in facts)
        assert {fact.fact_type for fact in facts if fact is not None} == {
            "document_line.quantity",
            "document_line.unit_of_measure",
            "document_line.unit_price",
            "document_line.price_base_quantity",
        }


@PROPERTY_SETTINGS
@given(
    field=FIELD_STRATEGY,
    kind=PROVENANCE_KIND_STRATEGY.filter(lambda value: value != "direct"),
    ordered=st.integers(min_value=1, max_value=500),
    excess=st.integers(min_value=1, max_value=500),
)
def test_property_delivered_over_order_fails_closed_for_any_unqualified_required_input(
    field: str,
    kind: str,
    ordered: int,
    excess: int,
) -> None:
    order_kinds: dict[str, str] = {}
    delivery_kinds: dict[str, str] = {}
    target, source_field = field.split("_", 1)
    if source_field == "uom":
        source_field = "unit_of_measure"
    if target == "order":
        order_kinds[source_field] = kind
    else:
        delivery_kinds[source_field] = kind

    with _isolated_db() as db:
        scenario = _DeliveredScenario(db, token="property-hostile")
        scenario.add_line_document(
            0,
            role="order",
            quantity=Decimal(ordered),
            kinds=order_kinds,
        )
        scenario.add_line_document(
            1,
            role="delivery",
            quantity=Decimal(ordered + excess),
            kinds=delivery_kinds,
        )
        scenario.analyze()

        assert scenario.case() is not None
        assert scenario.findings() == []


class DeliveredOverOrderProvenanceStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._db_context = _isolated_db()
        self.db = self._db_context.__enter__()
        self.scenario = _DeliveredScenario(self.db, token="stateful")
        self.scenario.add_line_document(
            0,
            role="order",
            quantity=Decimal("10"),
        )
        self.scenario.add_line_document(
            1,
            role="delivery",
            quantity=Decimal("12"),
        )
        self.scenario.analyze()
        self.next_index = 2
        self.dirty_since_analysis = False
        self.finding_history: dict[str, tuple] = {}
        self.judgment_history: dict[str, tuple] = {}
        self._remember_history()

    def teardown(self):
        self._db_context.__exit__(None, None, None)

    def _finding_snapshot(self, finding: ProvenanceFinding) -> tuple:
        links = list(
            self.db.scalars(
                select(ProvenanceFindingFact).where(
                    ProvenanceFindingFact.tenant_id == finding.tenant_id,
                    ProvenanceFindingFact.finding_id == finding.id,
                )
            )
        )
        return (
            finding.id,
            finding.version,
            finding.supersedes_finding_id,
            finding.rule_id,
            finding.rule_version,
            finding.rule_configuration_hash,
            tuple(sorted(link.fact_id for link in links)),
        )

    @staticmethod
    def _judgment_snapshot(judgment: ProvenanceJudgment) -> tuple:
        return (
            judgment.id,
            judgment.finding_id,
            judgment.review_decision_id,
            judgment.decision,
            judgment.reason,
        )

    def _remember_history(self) -> None:
        for finding in self.scenario.findings():
            self.finding_history.setdefault(
                finding.id,
                self._finding_snapshot(finding),
            )
        judgments = list(
            self.db.scalars(select(ProvenanceJudgment).where(ProvenanceJudgment.tenant_id == self.scenario.tenant.id))
        )
        for judgment in judgments:
            self.judgment_history.setdefault(
                judgment.id,
                self._judgment_snapshot(judgment),
            )

    @precondition(lambda self: self.next_index < 7)
    @rule(
        quantity=st.integers(min_value=1, max_value=20),
        kind=PROVENANCE_KIND_STRATEGY,
    )
    def add_delivery(self, quantity: int, kind: str) -> None:
        self.scenario.add_line_document(
            self.next_index,
            role="delivery",
            quantity=Decimal(quantity),
            kinds={"quantity": kind},
        )
        self.next_index += 1
        self.dirty_since_analysis = True

    @rule()
    def reanalyze(self) -> None:
        self.scenario.analyze()
        self.dirty_since_analysis = False
        self._remember_history()

    @rule()
    def record_human_judgment(self) -> None:
        expected = not self.dirty_since_analysis and self.scenario.all_support_is_direct()
        judgment = self.scenario.review(note=f"Stateful delivered review {len(self.judgment_history) + 1}.")
        assert (judgment is not None) is expected
        if judgment is not None:
            latest = self.scenario.findings()[-1]
            assert judgment.finding_id == latest.id
            assert (
                delivered_over_order_finding_matches_current_support(
                    self.db,
                    finding=latest,
                )
                is True
            )
        self._remember_history()

    @invariant()
    def references_resolve_and_recorded_history_is_immutable(self) -> None:
        tenant_id = self.scenario.tenant.id
        links = self.db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.tenant_id == tenant_id))
        for link in links:
            assert self.db.get(ProvenanceFinding, link.finding_id) is not None
            assert self.db.get(ProvenanceFact, link.fact_id) is not None
        for finding_id, snapshot in self.finding_history.items():
            finding = self.db.get(ProvenanceFinding, finding_id)
            assert finding is not None
            assert self._finding_snapshot(finding) == snapshot
        for judgment_id, snapshot in self.judgment_history.items():
            judgment = self.db.get(ProvenanceJudgment, judgment_id)
            assert judgment is not None
            assert self._judgment_snapshot(judgment) == snapshot

    @invariant()
    def finding_versions_are_linear_and_supersession_is_append_only(self) -> None:
        findings = self.scenario.findings()
        assert [finding.version for finding in findings] == list(range(1, len(findings) + 1))
        if findings:
            assert findings[0].supersedes_finding_id is None
        for previous, current in zip(findings, findings[1:], strict=False):
            assert current.supersedes_finding_id == previous.id


TestDeliveredOverOrderProvenanceStateMachine = DeliveredOverOrderProvenanceStateMachine.TestCase
TestDeliveredOverOrderProvenanceStateMachine.settings = STATEFUL_SETTINGS
