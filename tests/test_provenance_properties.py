from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager

from hypothesis import HealthCheck, example, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import ChainDocument, DiscrepancyCase, Document, OperationChain, ReviewDecision, Tenant, User, utcnow
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


settings.register_profile(
    "provenance-pr",
    max_examples=200,
    stateful_step_count=25,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
settings.register_profile(
    "provenance-deep",
    max_examples=2000,
    stateful_step_count=75,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
settings.load_profile(
    "provenance-deep" if os.environ.get("THISTINTI_HYPOTHESIS_PROFILE") == "deep" else "provenance-pr"
)


PROVENANCE_KINDS = (
    "direct",
    "external_unavailable",
    "human",
    "legacy",
    "missing",
    "wrong_value",
    "missing_locator",
)
KIND_STRATEGY = st.sampled_from(PROVENANCE_KINDS)
NUMBER_STRATEGY = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_",
    min_size=1,
    max_size=12,
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
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"thistinti-provenance-property:{key}"))


class _Scenario:
    def __init__(self, db: Session, *, token: str, number: str):
        self.db = db
        self.token = token
        self.number = number
        self.tenant = Tenant(id=_stable_id(token, "tenant"), name=f"Property {token}")
        self.user = User(
            id=_stable_id(token, "user"),
            tenant_id=self.tenant.id,
            email=f"{_stable_id(token, 'email')}@example.com",
            password_hash="property-test-only",
            role="reviewer",
        )
        self.chain = OperationChain(
            id=_stable_id(token, "chain"),
            tenant_id=self.tenant.id,
            reference_key=f"PROP-{token}",
        )
        db.add(self.tenant)
        db.flush()
        db.add(self.user)
        db.flush()
        db.add(self.chain)
        db.flush()
        self.kinds: dict[int, str] = {}

    def add_document(
        self,
        logical_index: int,
        *,
        number: str,
        kind: str,
        sequence_no: int | None = None,
    ) -> Document:
        document_id = _stable_id(self.token, "document", logical_index)
        digest = hashlib.sha256(f"{self.token}:{logical_index}:{number}".encode()).hexdigest()
        document = Document(
            id=document_id,
            tenant_id=self.tenant.id,
            document_type="order",
            number=number,
            currency="EUR",
            source_filename=f"property-{logical_index}.json",
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
                match_reason="property-test",
            )
        )
        self.db.flush()
        self._attach_number_fact(document, kind=kind)
        self.kinds[logical_index] = kind
        return document

    def _attach_number_fact(self, document: Document, *, kind: str) -> None:
        if kind == "missing":
            return

        if kind in {"direct", "external_unavailable", "wrong_value", "missing_locator"}:
            locator_status = "missing" if kind == "missing_locator" else "present"
            origin = create_origin(
                self.db,
                tenant_id=self.tenant.id,
                origin_type="DOCUMENT_EVIDENCE",
                source_ref=f"sha256:{document.file_hash}",
                document_id=document.id,
                source_availability="external_unavailable" if kind == "external_unavailable" else "available",
                locator_status=locator_status,
                locator_type="JSON_POINTER" if locator_status == "present" else None,
                locator_json='{"pointer":"/number"}' if locator_status == "present" else None,
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
                reason="Operator override used as hostile provenance input.",
                asserted_at=utcnow(),
            )
        elif kind == "legacy":
            origin = create_origin(
                self.db,
                tenant_id=self.tenant.id,
                origin_type="LEGACY_ORIGIN_UNKNOWN",
                legacy_marker=f"property:{document.id}",
            )
        else:
            raise AssertionError(f"unsupported property provenance kind: {kind}")

        value = f"{document.number}-WRONG" if kind == "wrong_value" else document.number
        append_fact(
            self.db,
            tenant_id=self.tenant.id,
            fact_key=f"document:{document.id}:number",
            fact_type="document.number",
            value_json=json.dumps(value),
            origin_id=origin.id,
        )

    def analyze(self) -> None:
        analyze_chain(self.db, self.chain)
        self.db.flush()

    def duplicate_case(self) -> DiscrepancyCase | None:
        return self.db.scalar(
            select(DiscrepancyCase).where(
                DiscrepancyCase.tenant_id == self.tenant.id,
                DiscrepancyCase.chain_id == self.chain.id,
                DiscrepancyCase.case_type == "duplicate_document_number",
            )
        )

    def findings(self) -> list[ProvenanceFinding]:
        case = self.duplicate_case()
        if case is None:
            return []
        return list(
            self.db.scalars(
                select(ProvenanceFinding)
                .where(
                    ProvenanceFinding.tenant_id == self.tenant.id,
                    ProvenanceFinding.case_id == case.id,
                )
                .order_by(ProvenanceFinding.version)
            )
        )

    def review(self, *, note: str, previous_state: str = "open") -> ProvenanceJudgment | None:
        case = self.duplicate_case()
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
            previous_state=previous_state,
        )


def _specs(data: tuple[int, tuple[str, ...], str]) -> list[tuple[str, str]]:
    duplicate_count, kinds, number = data
    result: list[tuple[str, str]] = []
    for index, kind in enumerate(kinds):
        document_number = number if index < duplicate_count else f"{number}-UNIQUE-{index}"
        result.append((document_number, kind))
    return result


@st.composite
def _document_sets(draw, *, require_duplicate: bool = False):
    total = draw(st.integers(min_value=2, max_value=6))
    minimum = 2 if require_duplicate else 0
    duplicate_count = draw(st.integers(min_value=minimum, max_value=total))
    kinds = tuple(draw(st.lists(KIND_STRATEGY, min_size=total, max_size=total)))
    number = draw(NUMBER_STRATEGY)
    return duplicate_count, kinds, number


@st.composite
def _permuted_duplicate_sets(draw):
    data = draw(_document_sets(require_duplicate=True))
    total = len(data[1])
    order = tuple(draw(st.permutations(tuple(range(total)))))
    return data, order


def _build_scenario(
    db: Session,
    data: tuple[int, tuple[str, ...], str],
    *,
    order: tuple[int, ...] | None = None,
    token: str = "scenario",
) -> _Scenario:
    specs = _specs(data)
    scenario = _Scenario(db, token=token, number=data[2])
    insertion_order = order if order is not None else tuple(range(len(specs)))
    for sequence_no, logical_index in enumerate(insertion_order, start=1):
        number, kind = specs[logical_index]
        scenario.add_document(
            logical_index,
            number=number,
            kind=kind,
            sequence_no=sequence_no,
        )
    return scenario


def _finding_snapshot(db: Session, finding: ProvenanceFinding) -> tuple:
    links = list(
        db.scalars(
            select(ProvenanceFindingFact).where(
                ProvenanceFindingFact.tenant_id == finding.tenant_id,
                ProvenanceFindingFact.finding_id == finding.id,
            )
        )
    )
    return (
        finding.id,
        finding.tenant_id,
        finding.case_id,
        finding.version,
        finding.rule_id,
        finding.rule_version,
        finding.rule_configuration_hash,
        finding.supersedes_finding_id,
        tuple(sorted((link.fact_id, link.role) for link in links)),
    )


def _judgment_snapshot(judgment: ProvenanceJudgment) -> tuple:
    return (
        judgment.id,
        judgment.tenant_id,
        judgment.finding_id,
        judgment.review_decision_id,
        judgment.reviewer_ref,
        judgment.reviewer_user_id,
        judgment.decision,
        judgment.reason,
        judgment.previous_state,
    )


def _semantic_snapshot(scenario: _Scenario) -> tuple:
    case = scenario.duplicate_case()
    if case is None:
        return scenario.chain.status, None, ()
    findings = []
    for finding in scenario.findings():
        fact_rows = []
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
            fact_rows.append((fact.fact_key, fact.value_json, link.role))
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


@given(data=_document_sets())
@example(data=(2, ("direct", "external_unavailable"), "EXT-UNAVAILABLE"))
def test_property_incomplete_or_unavailable_support_never_becomes_finding_provenance(data) -> None:
    duplicate_count, kinds, _number = data
    with _isolated_db() as db:
        scenario = _build_scenario(db, data)
        scenario.analyze()
        case = scenario.duplicate_case()
        findings = scenario.findings()

        if duplicate_count < 2:
            assert case is None
            assert findings == []
            return

        assert case is not None
        duplicate_kinds = kinds[:duplicate_count]
        if all(kind == "direct" for kind in duplicate_kinds):
            assert len(findings) == 1
            links = list(
                db.scalars(
                    select(ProvenanceFindingFact).where(
                        ProvenanceFindingFact.finding_id == findings[0].id,
                    )
                )
            )
            assert len(links) == duplicate_count
            for link in links:
                fact = db.get(ProvenanceFact, link.fact_id)
                assert fact is not None
                origin = db.get(ProvenanceOrigin, fact.origin_id)
                assert origin is not None
                assert origin.origin_type == "DOCUMENT_EVIDENCE"
                assert origin.source_availability == "available"
                assert origin.locator_status == "present"
        else:
            assert findings == []

        for fact in db.scalars(select(ProvenanceFact).where(ProvenanceFact.tenant_id == scenario.tenant.id)):
            origin = db.get(ProvenanceOrigin, fact.origin_id)
            assert origin is not None
            assert origin.tenant_id == fact.tenant_id


@given(data_and_order=_permuted_duplicate_sets())
def test_property_document_insertion_order_does_not_change_duplicate_provenance(data_and_order) -> None:
    data, order = data_and_order
    with _isolated_db() as db:
        baseline = _build_scenario(db, data, token="permutation")
        baseline.analyze()
        expected = _semantic_snapshot(baseline)

    with _isolated_db() as db:
        permuted = _build_scenario(db, data, order=order, token="permutation")
        permuted.analyze()
        assert _semantic_snapshot(permuted) == expected


@given(data=_document_sets(require_duplicate=True), repetitions=st.integers(min_value=1, max_value=5))
def test_property_reanalysis_is_idempotent(data, repetitions: int) -> None:
    with _isolated_db() as db:
        scenario = _build_scenario(db, data, token="idempotence")
        scenario.analyze()
        expected_semantics = _semantic_snapshot(scenario)
        expected_findings = [_finding_snapshot(db, finding) for finding in scenario.findings()]
        case = scenario.duplicate_case()
        assert case is not None
        case_id = case.id

        for _ in range(repetitions):
            scenario.analyze()

        assert _semantic_snapshot(scenario) == expected_semantics
        assert [_finding_snapshot(db, finding) for finding in scenario.findings()] == expected_findings
        cases = list(
            db.scalars(
                select(DiscrepancyCase).where(
                    DiscrepancyCase.tenant_id == scenario.tenant.id,
                    DiscrepancyCase.case_type == "duplicate_document_number",
                )
            )
        )
        assert [item.id for item in cases] == [case_id]


@given(later_count=st.integers(min_value=1, max_value=4), number=NUMBER_STRATEGY)
def test_property_new_support_versions_finding_without_mutating_history(later_count: int, number: str) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, token="history", number=number)
        scenario.add_document(0, number=number, kind="direct")
        scenario.add_document(1, number=number, kind="direct")
        scenario.analyze()

        first = scenario.findings()
        assert len(first) == 1
        first_snapshot = _finding_snapshot(db, first[0])

        for logical_index in range(2, 2 + later_count):
            scenario.add_document(logical_index, number=number, kind="direct")
        scenario.analyze()

        findings = scenario.findings()
        assert [finding.version for finding in findings] == [1, 2]
        assert findings[1].supersedes_finding_id == findings[0].id
        assert _finding_snapshot(db, findings[0]) == first_snapshot

        latest_links = list(
            db.scalars(
                select(ProvenanceFindingFact).where(
                    ProvenanceFindingFact.finding_id == findings[1].id,
                )
            )
        )
        assert len(latest_links) == 2 + later_count

        latest_snapshot = _finding_snapshot(db, findings[1])
        scenario.analyze()
        assert _finding_snapshot(db, findings[0]) == first_snapshot
        assert _finding_snapshot(db, scenario.findings()[1]) == latest_snapshot


@given(third_kind=KIND_STRATEGY, number=NUMBER_STRATEGY)
@example(third_kind="human", number="STALE-HUMAN")
def test_property_judgment_binds_only_to_exact_current_complete_finding(third_kind: str, number: str) -> None:
    with _isolated_db() as db:
        scenario = _Scenario(db, token="judgment", number=number)
        scenario.add_document(0, number=number, kind="direct")
        scenario.add_document(1, number=number, kind="direct")
        scenario.analyze()

        first_finding = scenario.findings()[0]
        first_judgment = scenario.review(note="Review of the initial complete finding.")
        assert first_judgment is not None
        assert first_judgment.finding_id == first_finding.id
        first_judgment_snapshot = _judgment_snapshot(first_judgment)

        scenario.add_document(2, number=number, kind=third_kind)
        scenario.analyze()
        second_judgment = scenario.review(
            note="Review after the duplicate support set changed.",
            previous_state="confirmed",
        )

        findings = scenario.findings()
        if third_kind == "direct":
            assert [finding.version for finding in findings] == [1, 2]
            assert second_judgment is not None
            assert second_judgment.finding_id == findings[1].id
        else:
            assert [finding.version for finding in findings] == [1]
            assert second_judgment is None

        persisted_first = db.get(ProvenanceJudgment, first_judgment.id)
        assert persisted_first is not None
        assert _judgment_snapshot(persisted_first) == first_judgment_snapshot
        assert persisted_first.finding_id == first_finding.id


class DuplicateNumberProvenanceStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._db_context = _isolated_db()
        self.db = self._db_context.__enter__()
        self.scenario = _Scenario(self.db, token="stateful", number="STATEFUL-DUP")
        self.scenario.add_document(0, number=self.scenario.number, kind="direct")
        self.scenario.add_document(1, number=self.scenario.number, kind="direct")
        self.scenario.analyze()
        self.next_index = 2
        self.dirty_since_analysis = False
        self.finding_history: dict[str, tuple] = {}
        self.judgment_history: dict[str, tuple] = {}
        self._remember_history()

    def teardown(self):
        self._db_context.__exit__(None, None, None)

    def _remember_history(self) -> None:
        for finding in self.scenario.findings():
            self.finding_history.setdefault(finding.id, _finding_snapshot(self.db, finding))
        judgments = list(
            self.db.scalars(
                select(ProvenanceJudgment).where(
                    ProvenanceJudgment.tenant_id == self.scenario.tenant.id,
                )
            )
        )
        for judgment in judgments:
            self.judgment_history.setdefault(judgment.id, _judgment_snapshot(judgment))

    def _support_is_current_and_complete(self) -> bool:
        return not self.dirty_since_analysis and all(kind == "direct" for kind in self.scenario.kinds.values())

    @precondition(lambda self: self.next_index < 6)
    @rule(kind=KIND_STRATEGY)
    def add_duplicate_document(self, kind: str) -> None:
        self.scenario.add_document(
            self.next_index,
            number=self.scenario.number,
            kind=kind,
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
        expected = self._support_is_current_and_complete()
        judgment = self.scenario.review(
            note=f"Stateful review {len(self.judgment_history) + 1}.",
            previous_state="open",
        )
        assert (judgment is not None) is expected
        if judgment is not None:
            latest = self.scenario.findings()[-1]
            assert judgment.finding_id == latest.id
        self._remember_history()

    @invariant()
    def references_always_resolve(self) -> None:
        tenant_id = self.scenario.tenant.id
        for fact in self.db.scalars(select(ProvenanceFact).where(ProvenanceFact.tenant_id == tenant_id)):
            origin = self.db.get(ProvenanceOrigin, fact.origin_id)
            assert origin is not None
            assert origin.tenant_id == tenant_id

        for link in self.db.scalars(select(ProvenanceFindingFact).where(ProvenanceFindingFact.tenant_id == tenant_id)):
            assert self.db.get(ProvenanceFinding, link.finding_id) is not None
            assert self.db.get(ProvenanceFact, link.fact_id) is not None

        for judgment in self.db.scalars(select(ProvenanceJudgment).where(ProvenanceJudgment.tenant_id == tenant_id)):
            finding = self.db.get(ProvenanceFinding, judgment.finding_id)
            review = self.db.get(ReviewDecision, judgment.review_decision_id)
            assert finding is not None
            assert review is not None
            assert finding.tenant_id == tenant_id
            assert review.tenant_id == tenant_id

    @invariant()
    def finding_versions_are_linear_and_history_is_immutable(self) -> None:
        findings = self.scenario.findings()
        assert [finding.version for finding in findings] == list(range(1, len(findings) + 1))
        if findings:
            assert findings[0].supersedes_finding_id is None
        for previous, current in zip(findings, findings[1:], strict=False):
            assert current.supersedes_finding_id == previous.id

        for finding_id, snapshot in self.finding_history.items():
            finding = self.db.get(ProvenanceFinding, finding_id)
            assert finding is not None
            assert _finding_snapshot(self.db, finding) == snapshot

        for judgment_id, snapshot in self.judgment_history.items():
            judgment = self.db.get(ProvenanceJudgment, judgment_id)
            assert judgment is not None
            assert _judgment_snapshot(judgment) == snapshot


TestDuplicateNumberProvenanceStateMachine = DuplicateNumberProvenanceStateMachine.TestCase
TestDuplicateNumberProvenanceStateMachine.settings = settings(
    max_examples=200,
    stateful_step_count=75 if os.environ.get("THISTINTI_HYPOTHESIS_PROFILE") == "deep" else 25,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
