from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager

from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import (
    ChainDocument,
    DiscrepancyCase,
    Document,
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
CURRENCY_STRATEGY = st.sampled_from(("EUR", "USD", "GBP"))
PROVENANCE_KIND_STRATEGY = st.sampled_from(
    ("direct", "missing", "external_unavailable", "human", "wrong_value", "missing_locator", "wrong_pointer")
)


def _json_payload(
    *,
    document_type: str,
    number: str,
    currency: str | None,
    order_number: str | None = None,
) -> bytes:
    data: dict[str, object] = {
        "document_type": document_type,
        "number": number,
        "document_date": "2026-08-29",
        "supplier_name": "Currency Provenance Supplier",
        "supplier_vat": "IT00000000029",
        "lines": [
            {
                "line_no": 1,
                "sku": "CUR-ITEM",
                "description": "Currency provenance item",
                "quantity": 1,
                "unit_price": 10,
                "discount_rate": 0,
                "tax_rate": 22,
                "line_total": 10,
            }
        ],
    }
    if currency is not None:
        data["currency"] = currency
    if order_number is not None:
        data["references"] = {"order_numbers": [order_number]}
    return json.dumps(data).encode("utf-8")


def _upload_json(
    client,
    auth,
    *,
    document_type: str,
    number: str,
    currency: str | None,
    order_number: str | None = None,
):
    return client.post(
        "/api/documents/upload",
        headers=auth,
        files={
            "file": (
                f"{number}.json",
                _json_payload(
                    document_type=document_type,
                    number=number,
                    currency=currency,
                    order_number=order_number,
                ),
                "application/json",
            )
        },
    )


def _currency_case(db: Session) -> DiscrepancyCase | None:
    return db.scalar(select(DiscrepancyCase).where(DiscrepancyCase.case_type == "currency_mismatch"))


def _finding_versions(db: Session, case: DiscrepancyCase) -> list[ProvenanceFinding]:
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


def test_currency_mismatch_end_to_end_binds_direct_currency_facts_and_judgment(client, auth):
    order = _upload_json(
        client,
        auth,
        document_type="order",
        number="PO-CURRENCY-1",
        currency="EUR",
    )
    invoice = _upload_json(
        client,
        auth,
        document_type="invoice",
        number="INV-CURRENCY-1",
        currency="USD",
        order_number="PO-CURRENCY-1",
    )
    assert order.status_code == 201, order.text
    assert invoice.status_code == 201, invoice.text
    document_ids = {order.json()["document"]["id"], invoice.json()["document"]["id"]}

    with SessionLocal() as db:
        case = _currency_case(db)
        assert case is not None
        findings = _finding_versions(db, case)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.rule_id == "builtin:currency_mismatch"
        assert finding.rule_version == "1"
        assert len(finding.rule_configuration_hash) == 64
        links = list(
            db.scalars(
                select(ProvenanceFindingFact).where(
                    ProvenanceFindingFact.tenant_id == case.tenant_id,
                    ProvenanceFindingFact.finding_id == finding.id,
                )
            )
        )
        assert len(links) == 2
        facts = [db.get(ProvenanceFact, link.fact_id) for link in links]
        assert all(fact is not None for fact in facts)
        assert {fact.fact_key for fact in facts if fact is not None} == {
            f"document:{document_id}:currency" for document_id in document_ids
        }
        assert {fact.value_json for fact in facts if fact is not None} == {'"EUR"', '"USD"'}
        for fact in facts:
            assert fact is not None
            origin = db.get(ProvenanceOrigin, fact.origin_id)
            assert origin is not None
            assert origin.origin_type == "DOCUMENT_EVIDENCE"
            assert origin.source_availability == "available"
            assert origin.locator_status == "present"
            assert origin.locator_type == "JSON_POINTER"
            assert origin.locator_json == '{"pointer":"/currency"}'

        case_id = case.id
        finding_id = finding.id

    reviewed = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "confirmed", "note": "Both explicit currencies checked against source evidence."},
    )
    assert reviewed.status_code == 200, reviewed.text
    with SessionLocal() as db:
        judgment = db.scalar(select(ProvenanceJudgment).where(ProvenanceJudgment.finding_id == finding_id))
        assert judgment is not None
        assert judgment.decision == "confirmed"


def test_currency_mismatch_provenance_fails_closed_when_one_currency_is_defaulted(client, auth):
    order = _upload_json(
        client,
        auth,
        document_type="order",
        number="PO-CURRENCY-DEFAULT",
        currency=None,
    )
    invoice = _upload_json(
        client,
        auth,
        document_type="invoice",
        number="INV-CURRENCY-DEFAULT",
        currency="USD",
        order_number="PO-CURRENCY-DEFAULT",
    )
    assert order.status_code == 201, order.text
    assert invoice.status_code == 201, invoice.text

    with SessionLocal() as db:
        case = _currency_case(db)
        assert case is not None
        assert _finding_versions(db, case) == []
        defaulted_document_id = order.json()["document"]["id"]
        defaulted_fact = db.scalar(
            select(ProvenanceFact).where(ProvenanceFact.fact_key == f"document:{defaulted_document_id}:currency")
        )
        assert defaulted_fact is None


def test_currency_mismatch_versions_when_complete_support_set_changes_and_reanalysis_is_idempotent(client, auth):
    assert (
        _upload_json(
            client,
            auth,
            document_type="order",
            number="PO-CURRENCY-VERSION",
            currency="EUR",
        ).status_code
        == 201
    )
    assert (
        _upload_json(
            client,
            auth,
            document_type="invoice",
            number="INV-CURRENCY-VERSION",
            currency="USD",
            order_number="PO-CURRENCY-VERSION",
        ).status_code
        == 201
    )

    with SessionLocal() as db:
        case = _currency_case(db)
        assert case is not None
        first = _finding_versions(db, case)
        assert [item.version for item in first] == [1]
        first_id = first[0].id

    delivery = _upload_json(
        client,
        auth,
        document_type="delivery",
        number="DDT-CURRENCY-VERSION",
        currency="GBP",
        order_number="PO-CURRENCY-VERSION",
    )
    assert delivery.status_code == 201, delivery.text

    with SessionLocal() as db:
        case = _currency_case(db)
        assert case is not None
        versions = _finding_versions(db, case)
        assert [item.version for item in versions] == [1, 2]
        assert versions[1].supersedes_finding_id == first_id
        latest_links = list(
            db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == versions[1].id))
        )
        assert len(latest_links) == 3
        chain = db.get(OperationChain, case.chain_id)
        assert chain is not None
        analyze_chain(db, chain)
        db.flush()
        assert [item.version for item in _finding_versions(db, case)] == [1, 2]


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
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"thistinti-currency-provenance:{key}"))


class _CurrencyScenario:
    def __init__(self, db: Session, *, token: str):
        self.db = db
        self.token = token
        self.tenant = Tenant(id=_stable_id(token, "tenant"), name=f"Currency {token}")
        self.user = User(
            id=_stable_id(token, "user"),
            tenant_id=self.tenant.id,
            email=f"{_stable_id(token, 'email')}@example.com",
            password_hash="currency-property-test-only",
            role="reviewer",
        )
        self.chain = OperationChain(
            id=_stable_id(token, "chain"),
            tenant_id=self.tenant.id,
            reference_key=f"CUR-{token}",
        )
        db.add(self.tenant)
        db.flush()
        db.add(self.user)
        db.flush()
        db.add(self.chain)
        db.flush()
        self.kinds: dict[int, str] = {}
        self.currencies: dict[int, str] = {}

    def add_document(
        self,
        logical_index: int,
        *,
        currency: str,
        kind: str,
        sequence_no: int | None = None,
    ) -> Document:
        document_id = _stable_id(self.token, "document", logical_index)
        digest = hashlib.sha256(f"{self.token}:{logical_index}:{currency}".encode()).hexdigest()
        document = Document(
            id=document_id,
            tenant_id=self.tenant.id,
            document_type="order",
            number=f"CUR-DOC-{logical_index}",
            currency=currency,
            source_filename=f"currency-{logical_index}.json",
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
                role="order",
                sequence_no=sequence_no if sequence_no is not None else logical_index + 1,
                match_confidence=1.0,
                match_reason="currency-property-test",
            )
        )
        self.db.flush()
        self._attach_currency_fact(document, kind=kind)
        self.kinds[logical_index] = kind
        self.currencies[logical_index] = currency
        return document

    def _attach_currency_fact(self, document: Document, *, kind: str) -> None:
        if kind == "missing":
            return
        if kind in {"direct", "external_unavailable", "wrong_value", "missing_locator", "wrong_pointer"}:
            locator_status = "missing" if kind == "missing_locator" else "present"
            pointer = "/other" if kind == "wrong_pointer" else "/currency"
            origin = create_origin(
                self.db,
                tenant_id=self.tenant.id,
                origin_type="DOCUMENT_EVIDENCE",
                source_ref=f"sha256:{document.file_hash}",
                document_id=document.id,
                source_availability="external_unavailable" if kind == "external_unavailable" else "available",
                locator_status=locator_status,
                locator_type="JSON_POINTER" if locator_status == "present" else None,
                locator_json=json.dumps({"pointer": pointer}, separators=(",", ":")) if locator_status == "present" else None,
            )
        elif kind == "human":
            origin = create_origin(
                self.db,
                tenant_id=self.tenant.id,
                origin_type="HUMAN_ASSERTION",
                actor_ref=f"user:{self.user.id}",
                actor_user_id=self.user.id,
                reason="Hostile manual currency input.",
                asserted_at=utcnow(),
            )
        else:
            raise AssertionError(f"unsupported provenance kind: {kind}")

        value = "JPY" if kind == "wrong_value" else document.currency
        append_fact(
            self.db,
            tenant_id=self.tenant.id,
            fact_key=f"document:{document.id}:currency",
            fact_type="document.currency",
            value_json=json.dumps(value),
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
                DiscrepancyCase.case_type == "currency_mismatch",
            )
        )

    def findings(self) -> list[ProvenanceFinding]:
        case = self.case()
        if case is None:
            return []
        return _finding_versions(self.db, case)

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


def _currency_semantic_snapshot(scenario: _CurrencyScenario) -> tuple:
    case = scenario.case()
    if case is None:
        return scenario.chain.status, None, ()
    findings = []
    for finding in scenario.findings():
        fact_rows: list[tuple[str, str]] = []
        links = list(
            scenario.db.scalars(
                select(ProvenanceFindingFact).where(
                    ProvenanceFindingFact.tenant_id == scenario.tenant.id,
                    ProvenanceFindingFact.finding_id == finding.id,
                )
            )
        )
        for link in links:
            fact = scenario.db.get(ProvenanceFact, link.fact_id)
            assert fact is not None
            fact_rows.append((fact.fact_key, fact.value_json))
        findings.append(
            (
                finding.version,
                finding.rule_id,
                finding.rule_version,
                finding.rule_configuration_hash,
                tuple(sorted(fact_rows)),
            )
        )
    return scenario.chain.status, (case.case_type, case.status, case.fingerprint), tuple(findings)


@st.composite
def _currency_document_sets(draw):
    total = draw(st.integers(min_value=2, max_value=5))
    currencies = tuple(draw(st.lists(CURRENCY_STRATEGY, min_size=total, max_size=total)))
    kinds = tuple(draw(st.lists(PROVENANCE_KIND_STRATEGY, min_size=total, max_size=total)))
    return currencies, kinds


@PROPERTY_SETTINGS
@given(data=_currency_document_sets())
def test_property_currency_mismatch_requires_complete_direct_support_for_every_engine_input(data) -> None:
    currencies, kinds = data
    with _isolated_db() as db:
        scenario = _CurrencyScenario(db, token="property")
        for index, (currency, kind) in enumerate(zip(currencies, kinds, strict=True)):
            scenario.add_document(index, currency=currency, kind=kind)
        scenario.analyze()

        if len(set(currencies)) < 2:
            assert scenario.case() is None
            assert scenario.findings() == []
        else:
            assert scenario.case() is not None
            if all(kind == "direct" for kind in kinds):
                findings = scenario.findings()
                assert len(findings) == 1
                links = list(
                    db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.finding_id == findings[0].id))
                )
                assert len(links) == len(currencies)
            else:
                assert scenario.findings() == []


@PROPERTY_SETTINGS
@given(data=_currency_document_sets(), order_seed=st.integers(min_value=0, max_value=10_000))
def test_property_currency_provenance_is_independent_of_document_insertion_order(data, order_seed: int) -> None:
    currencies, kinds = data
    order = list(range(len(currencies)))
    order.sort(key=lambda index: hashlib.sha256(f"{order_seed}:{index}".encode()).hexdigest())

    with _isolated_db() as db:
        baseline = _CurrencyScenario(db, token="permutation")
        for index, (currency, kind) in enumerate(zip(currencies, kinds, strict=True)):
            baseline.add_document(index, currency=currency, kind=kind, sequence_no=index + 1)
        baseline.analyze()
        expected = _currency_semantic_snapshot(baseline)

    with _isolated_db() as db:
        permuted = _CurrencyScenario(db, token="permutation")
        for sequence_no, logical_index in enumerate(order, start=1):
            permuted.add_document(
                logical_index,
                currency=currencies[logical_index],
                kind=kinds[logical_index],
                sequence_no=sequence_no,
            )
        permuted.analyze()
        assert _currency_semantic_snapshot(permuted) == expected


class CurrencyMismatchProvenanceStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._db_context = _isolated_db()
        self.db = self._db_context.__enter__()
        self.scenario = _CurrencyScenario(self.db, token="stateful")
        self.scenario.add_document(0, currency="EUR", kind="direct")
        self.scenario.add_document(1, currency="USD", kind="direct")
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
            self.finding_history.setdefault(finding.id, self._finding_snapshot(finding))
        judgments = list(
            self.db.scalars(
                select(ProvenanceJudgment).where(ProvenanceJudgment.tenant_id == self.scenario.tenant.id)
            )
        )
        for judgment in judgments:
            self.judgment_history.setdefault(judgment.id, self._judgment_snapshot(judgment))

    def _support_is_current_and_complete(self) -> bool:
        return not self.dirty_since_analysis and all(kind == "direct" for kind in self.scenario.kinds.values())

    @precondition(lambda self: self.next_index < 6)
    @rule(currency=CURRENCY_STRATEGY, kind=PROVENANCE_KIND_STRATEGY)
    def add_currency_document(self, currency: str, kind: str) -> None:
        self.scenario.add_document(self.next_index, currency=currency, kind=kind)
        self.next_index += 1
        self.dirty_since_analysis = True

    @rule()
    def reanalyze(self) -> None:
        self.scenario.analyze()
        self.dirty_since_analysis = False
        self._remember_history()

    @rule()
    def record_human_judgment(self) -> None:
        expected = self._support_is_current_and_complete()
        judgment = self.scenario.review(note=f"Stateful currency review {len(self.judgment_history) + 1}.")
        assert (judgment is not None) is expected
        if judgment is not None:
            assert judgment.finding_id == self.scenario.findings()[-1].id
        self._remember_history()

    @invariant()
    def references_resolve_and_history_is_immutable(self) -> None:
        tenant_id = self.scenario.tenant.id
        for link in self.db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.tenant_id == tenant_id)):
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
    def finding_versions_are_linear_and_never_duplicate_current_support(self) -> None:
        findings = self.scenario.findings()
        assert [finding.version for finding in findings] == list(range(1, len(findings) + 1))
        if findings:
            assert findings[0].supersedes_finding_id is None
        for previous, current in zip(findings, findings[1:], strict=False):
            assert current.supersedes_finding_id == previous.id


TestCurrencyMismatchProvenanceStateMachine = CurrencyMismatchProvenanceStateMachine.TestCase
TestCurrencyMismatchProvenanceStateMachine.settings = STATEFUL_SETTINGS
