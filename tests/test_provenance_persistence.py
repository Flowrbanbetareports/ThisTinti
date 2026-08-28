from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import DiscrepancyCase, Document, OperationChain, ReviewDecision, Tenant, User, utcnow
from app.provenance_models import (
    ProvenanceDerivation,
    ProvenanceDerivationInput,
    ProvenanceFact,
    ProvenanceFinding,
    ProvenanceJudgment,
    ProvenanceOrigin,
)
from app.services.provenance import (
    ProvenanceContractError,
    append_fact,
    create_derivation,
    create_origin,
    record_finding,
    record_judgment,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _seed_case(db):
    tenant = Tenant(name="Provenance Test")
    db.add(tenant)
    db.flush()
    user = User(
        tenant_id=tenant.id,
        email="prov@example.com",
        password_hash="not-used-in-this-test",
        role="reviewer",
    )
    document = Document(
        tenant_id=tenant.id,
        document_type="order",
        source_filename="order.json",
        storage_path="/tmp/order.json",
        file_hash=HASH_A,
        parse_status="parsed",
    )
    db.add_all([user, document])
    db.flush()
    chain = OperationChain(tenant_id=tenant.id, reference_key="PROV-1")
    db.add(chain)
    db.flush()
    case = DiscrepancyCase(
        tenant_id=tenant.id,
        chain_id=chain.id,
        fingerprint=HASH_B,
        case_type="amount_mismatch",
        title="Importo non coerente",
        explanation="Fixture provenance",
    )
    db.add(case)
    db.flush()
    return tenant, user, document, case


def test_complete_provenance_graph_is_persisted_without_overwriting_history():
    with SessionLocal() as db:
        tenant, user, document, case = _seed_case(db)
        document_origin = create_origin(
            db,
            tenant_id=tenant.id,
            origin_type="DOCUMENT_EVIDENCE",
            source_ref=f"document:{document.id}",
            document_id=document.id,
            source_availability="available",
            locator_status="present",
            locator_type="JSON_POINTER",
            locator_json='{"pointer":"/number"}',
            engine_id="native-json-parser",
            engine_version="1",
            configuration_hash=HASH_A,
        )
        source_fact = append_fact(
            db,
            tenant_id=tenant.id,
            fact_key=f"document:{document.id}:number",
            fact_type="document.number",
            value_json='"PO-100"',
            origin_id=document_origin.id,
        )
        derivation = create_derivation(
            db,
            tenant_id=tenant.id,
            input_fact_ids=[source_fact.id],
            transformation_id="normalize.order_number",
            engine_id="thistinti.rules",
            engine_version="0.1",
            configuration_hash=HASH_B,
        )
        derived_origin = create_origin(
            db,
            tenant_id=tenant.id,
            origin_type="DETERMINISTIC_DERIVATION",
            derivation_id=derivation.id,
        )
        derived_fact = append_fact(
            db,
            tenant_id=tenant.id,
            fact_key=f"document:{document.id}:normalized_number",
            fact_type="document.normalized_number",
            value_json='"PO100"',
            origin_id=derived_origin.id,
        )
        finding = record_finding(
            db,
            tenant_id=tenant.id,
            case_id=case.id,
            input_fact_ids=[source_fact.id, derived_fact.id],
            rule_id="PROC.ORDER_NUMBER.COHERENCE",
            rule_version="0.1.0",
            rule_configuration_hash=HASH_C,
        )
        review = ReviewDecision(
            tenant_id=tenant.id,
            case_id=case.id,
            user_id=user.id,
            decision="confirmed",
            note="Confermato dal revisore",
        )
        db.add(review)
        db.flush()
        judgment = record_judgment(
            db,
            tenant_id=tenant.id,
            finding_id=finding.id,
            review_decision_id=review.id,
            reviewer_ref=f"user:{user.id}",
            reviewer_user_id=user.id,
            decision="confirmed",
            reason="Confermato confrontando il documento originale.",
            previous_state="open",
        )
        db.commit()

        assert db.get(ProvenanceOrigin, document_origin.id).origin_type == "DOCUMENT_EVIDENCE"
        assert db.get(ProvenanceDerivation, derivation.id).configuration_hash == HASH_B
        assert db.get(ProvenanceFact, source_fact.id).version == 1
        assert db.get(ProvenanceFinding, finding.id).rule_version == "0.1.0"
        assert db.get(ProvenanceJudgment, judgment.id).previous_state == "open"

        human_origin = create_origin(
            db,
            tenant_id=tenant.id,
            origin_type="HUMAN_ASSERTION",
            actor_ref=f"user:{user.id}",
            actor_user_id=user.id,
            reason="Correzione esplicita del numero ordine.",
            asserted_at=utcnow(),
        )
        revised = append_fact(
            db,
            tenant_id=tenant.id,
            fact_key=source_fact.fact_key,
            fact_type=source_fact.fact_type,
            value_json='"PO-101"',
            origin_id=human_origin.id,
            supersedes_fact_id=source_fact.id,
        )
        db.commit()
        assert revised.version == 2
        assert revised.supersedes_fact_id == source_fact.id
        assert db.get(ProvenanceFact, source_fact.id).value_json == '"PO-100"'


def test_existing_fact_requires_explicit_supersession():
    with SessionLocal() as db:
        tenant, _user, _document, _case = _seed_case(db)
        legacy = create_origin(
            db,
            tenant_id=tenant.id,
            origin_type="LEGACY_ORIGIN_UNKNOWN",
            legacy_marker="pre-provenance-runtime",
        )
        fact = append_fact(
            db,
            tenant_id=tenant.id,
            fact_key="legacy:amount",
            fact_type="amount",
            value_json="12.50",
            origin_id=legacy.id,
        )
        assert fact.version == 1
        assert legacy.origin_type == "LEGACY_ORIGIN_UNKNOWN"
        with pytest_raises_contract("superseded explicitly"):
            append_fact(
                db,
                tenant_id=tenant.id,
                fact_key="legacy:amount",
                fact_type="amount",
                value_json="13.00",
                origin_id=legacy.id,
            )


def test_origin_and_derivation_validation_rejects_implicit_or_orphaned_provenance():
    with SessionLocal() as db:
        tenant, user, _document, _case = _seed_case(db)
        with pytest_raises_contract("reason is required"):
            create_origin(
                db,
                tenant_id=tenant.id,
                origin_type="HUMAN_ASSERTION",
                actor_ref=f"user:{user.id}",
                actor_user_id=user.id,
                asserted_at=utcnow(),
            )
        with pytest_raises_contract("at least one input fact"):
            create_derivation(
                db,
                tenant_id=tenant.id,
                input_fact_ids=[],
                transformation_id="empty",
                engine_id="test",
                engine_version="1",
                configuration_hash=HASH_A,
            )


def test_database_foreign_keys_reject_orphaned_derivation_inputs():
    with SessionLocal() as db:
        tenant, _user, _document, _case = _seed_case(db)
        derivation = ProvenanceDerivation(
            tenant_id=tenant.id,
            transformation_id="test",
            engine_id="test",
            engine_version="1",
            configuration_hash=HASH_A,
        )
        db.add(derivation)
        db.flush()
        db.add(
            ProvenanceDerivationInput(
                tenant_id=tenant.id,
                derivation_id=derivation.id,
                fact_id="00000000-0000-0000-0000-000000000000",
                position=1,
            )
        )
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("orphaned provenance input was accepted")


class pytest_raises_contract:
    def __init__(self, match: str):
        self.match = match

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, _traceback):
        if exc_type is None:
            raise AssertionError("ProvenanceContractError was not raised")
        if not issubclass(exc_type, ProvenanceContractError):
            return False
        assert self.match in str(exc)
        return True
