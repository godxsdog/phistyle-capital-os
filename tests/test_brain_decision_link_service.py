import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import brain_review, decision_request, knowledge, triage  # noqa: F401
from shared.models.knowledge import DecisionLog, DecisionStatus
from shared.services.brain_decision_link_service import (
    BrainReviewDecisionLogLinkStaleError,
    BrainReviewDecisionRequestMissingError,
    BrainReviewNotFoundError,
    create_decision_log_draft_from_brain_review,
)
from shared.services.brain_review_service import create_brain_review
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


def create_request_and_review(session, *, proposed_decision_log_id=None):
    request = create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status="submitted",
    )
    review = create_brain_review(
        session,
        decision_request_id=request.id,
        recommendation="human_review_required",
        rationale="High risk concentration.",
        confidence="medium",
        risks="concentration",
        required_human_approval=True,
        proposed_decision_log_id=proposed_decision_log_id,
        created_by="brain-orchestrator",
    )
    return request, review


def test_create_decision_log_draft_from_brain_review():
    session = make_session()
    request, review = create_request_and_review(session)

    result = create_decision_log_draft_from_brain_review(
        session,
        brain_review_id=review.id,
        proposed_by="Kaichang",
    )

    session.refresh(review)
    decision_log = session.get(DecisionLog, result.decision_log_id)
    assert result.created is True
    assert review.proposed_decision_log_id == decision_log.id
    assert decision_log.status == DecisionStatus.PROPOSED
    assert decision_log.approved_by is None
    assert decision_log.title == request.question
    assert decision_log.decision == review.recommendation.value
    assert decision_log.rationale == review.rationale
    assert decision_log.proposed_by == "Kaichang"
    assert decision_log.related_request_id == str(request.id)


def test_second_call_returns_existing_draft_without_duplicate():
    session = make_session()
    _, review = create_request_and_review(session)

    first = create_decision_log_draft_from_brain_review(session, brain_review_id=review.id)
    second = create_decision_log_draft_from_brain_review(session, brain_review_id=review.id)

    assert first.created is True
    assert second.created is False
    assert first.decision_log_id == second.decision_log_id
    assert session.query(DecisionLog).count() == 1


def test_omitted_proposed_by_uses_brain_review_created_by():
    session = make_session()
    _, review = create_request_and_review(session)

    result = create_decision_log_draft_from_brain_review(session, brain_review_id=review.id)

    decision_log = session.get(DecisionLog, result.decision_log_id)
    assert decision_log.proposed_by == "brain-orchestrator"


def test_invalid_brain_review_id_rejected():
    session = make_session()

    with pytest.raises(BrainReviewNotFoundError):
        create_decision_log_draft_from_brain_review(session, brain_review_id=999)


def test_missing_decision_request_rejected_without_partial_decision_log():
    session = make_session()
    _, review = create_request_and_review(session)
    session.query(decision_request.DecisionRequest).delete()
    session.commit()

    with pytest.raises(BrainReviewDecisionRequestMissingError):
        create_decision_log_draft_from_brain_review(session, brain_review_id=review.id)
    assert session.query(DecisionLog).count() == 0


def test_stale_decision_log_link_rejected_without_replacement():
    session = make_session()
    _, review = create_request_and_review(session)
    review.proposed_decision_log_id = 999
    session.commit()

    with pytest.raises(BrainReviewDecisionLogLinkStaleError):
        create_decision_log_draft_from_brain_review(session, brain_review_id=review.id)
    session.refresh(review)
    assert review.proposed_decision_log_id == 999
    assert session.query(DecisionLog).count() == 0

