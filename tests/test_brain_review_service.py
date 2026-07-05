import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import brain_review, decision_request, knowledge, triage  # noqa: F401
from shared.services.brain_review_service import (
    create_brain_review,
    get_latest_brain_review_for_request,
    list_brain_reviews,
    list_brain_reviews_for_request,
)
from shared.services.decision_request_service import create_decision_request


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def create_request(session):
    return create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status="submitted",
    )


def test_create_list_and_latest_brain_review():
    session = make_session()
    request = create_request(session)

    first = create_brain_review(
        session,
        decision_request_id=request.id,
        recommendation="human_review_required",
        rationale="High risk.",
        confidence="medium",
        risks=["concentration", "market-volatility"],
        required_human_approval=True,
        created_by="brain-orchestrator",
    )
    second = create_brain_review(
        session,
        decision_request_id=request.id,
        recommendation="defer",
        rationale="Needs worker prep.",
        confidence="medium",
        risks="needs-summary",
        required_human_approval=True,
        created_by="human",
    )

    assert list_brain_reviews(session)[0].id == first.id
    assert len(list_brain_reviews_for_request(session, request.id)) == 2
    assert get_latest_brain_review_for_request(session, request.id).id == second.id
    assert first.risks == "concentration,market-volatility"


def test_create_brain_review_persists_optional_llm_metadata():
    session = make_session()
    request = create_request(session)

    review = create_brain_review(
        session,
        decision_request_id=request.id,
        recommendation="human_review_required",
        rationale="LLM-backed review.",
        confidence="high",
        risks=["concentration"],
        required_human_approval=True,
        created_by="brain-orchestrator",
        llm_backed=True,
        llm_provider="deepseek",
        llm_model="deepseek-reasoner",
        llm_fallback_reason=None,
        llm_floor_applied=False,
    )

    assert review.llm_backed is True
    assert review.llm_provider == "deepseek"
    assert review.llm_model == "deepseek-reasoner"
    assert review.llm_fallback_reason is None
    assert review.llm_floor_applied is False
