from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscrepancyCase, OperationChain, Tenant, User
from app.rc15_models import RC15CaseEconomicAssessment, RC15IntakeRecord
from app.services.rc15 import economic_assessment_payload, set_economic_assessment, transition_case


def _seed_case():
    with SessionLocal() as db:
        tenant = Tenant(name="RC15 Test")
        db.add(tenant)
        db.flush()
        user = User(tenant_id=tenant.id, email="rc15@example.com", password_hash="x", role="admin")
        db.add(user)
        chain = OperationChain(tenant_id=tenant.id, reference_key="RC15-CASE")
        db.add(chain)
        db.flush()
        case = DiscrepancyCase(
            tenant_id=tenant.id,
            chain_id=chain.id,
            fingerprint="a" * 64,
            case_type="quantity_mismatch",
            severity="high",
            title="Mismatch",
            explanation="Mismatch",
        )
        db.add(case)
        db.commit()
        return tenant.id, user.id, case.id


def test_economic_unknown_is_distinct_from_confirmed_zero():
    tenant_id, user_id, case_id = _seed_case()
    with SessionLocal() as db:
        unknown = set_economic_assessment(
            db,
            tenant_id,
            user_id,
            case_id,
            state="unknown",
            potential_exposure=None,
            confirmed_loss=None,
            currency="EUR",
            note="Importo non determinabile",
        )
        assert economic_assessment_payload(unknown)["state"] == "unknown"
        assert unknown.confirmed_loss is None
        zero = set_economic_assessment(
            db,
            tenant_id,
            user_id,
            case_id,
            state="confirmed_zero",
            potential_exposure=None,
            confirmed_loss=Decimal("0"),
            currency="EUR",
            note="Nessuna perdita confermata",
        )
        assert economic_assessment_payload(zero)["state"] == "confirmed_zero"
        assert zero.confirmed_loss == Decimal("0")


def test_economic_state_rejects_ambiguous_values():
    tenant_id, user_id, case_id = _seed_case()
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            set_economic_assessment(
                db,
                tenant_id,
                user_id,
                case_id,
                state="unknown",
                potential_exposure=Decimal("10"),
                confirmed_loss=None,
                currency="EUR",
                note="Valore ambiguo",
            )


def test_case_reopen_preserves_human_history():
    tenant_id, user_id, case_id = _seed_case()
    with SessionLocal() as db:
        transition_case(db, tenant_id, user_id, case_id, "confirmed", "Confermata sui documenti")
        transition_case(db, tenant_id, user_id, case_id, "resolved", "Correzione completata")
        item = transition_case(db, tenant_id, user_id, case_id, "reopen", "Nuova evidenza ricevuta")
        assert item.status == "needs_review"
        from app.models import ReviewDecision

        history = list(db.scalars(select(ReviewDecision).where(ReviewDecision.case_id == case_id)))
        assert [entry.decision for entry in history] == ["confirmed", "resolved", "needs_review"]


def test_intake_human_classification_is_separate_data():
    assert RC15IntakeRecord.__tablename__ == "rc15_intake_records"
    assert {"subject_id", "state", "category"}.issubset(RC15IntakeRecord.__table__.columns.keys())


def test_economic_state_is_persisted_explicitly():
    assert "state" in RC15CaseEconomicAssessment.__table__.columns
