import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import brain_review, decision_request, human_review, knowledge, triage  # noqa: F401
from shared.models.decision_request import DecisionRequest, DecisionRequestStatus
from shared.models.human_review import HumanReview, HumanReviewDecision
from shared.models.knowledge import DecisionLog, DecisionStatus
from shared.services.decision_request_service import create_decision_request
from shared.services.human_review_service import (
    DecisionLogNotFoundError,
    DecisionLogNotReviewableError,
    HumanReviewAlreadyExistsError,
    HumanReviewValidationError,
    RelatedDecisionRequestMalformedError,
    RelatedDecisionRequestMissingError,
    list_human_reviews,
    list_human_reviews_for_decision_log,
    review_decision_log,
)
from shared.services.knowledge_service import create_decision_log


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


def create_request_and_proposed_decision(session):
    request = create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status="submitted",
        created_by="Kaichang",
    )
    decision_log = create_decision_log(
        session,
        title=request.question,
        decision="human_review_required",
        rationale="High risk concentration.",
        proposed_by="brain-orchestrator",
        reviewed_by="brain-orchestrator",
        status="proposed",
        related_request_id=str(request.id),
    )
    return request, decision_log


def test_approve_proposed_decision_log_creates_human_review_and_updates_records():
    session = make_session()
    request, decision_log = create_request_and_proposed_decision(session)

    result = review_decision_log(
        session,
        decision_log_id=decision_log.id,
        reviewer="  Kaichang  ",
        review_decision="approve",
        comment="Reviewed and approved as a decision record.",
    )

    session.refresh(decision_log)
    session.refresh(request)
    human_reviews = list_human_reviews(session)
    assert result.review_decision == "approve"
    assert result.decision_log_status == "approved"
    assert result.decision_request_status == "human_approved"
    assert len(human_reviews) == 1
    assert human_reviews[0].decision_log_id == decision_log.id
    assert human_reviews[0].decision_request_id == request.id
    assert human_reviews[0].reviewer == "Kaichang"
    assert human_reviews[0].review_decision == HumanReviewDecision.APPROVE
    assert decision_log.status == DecisionStatus.APPROVED
    assert decision_log.approved_by == "Kaichang"
    assert request.status == DecisionRequestStatus.HUMAN_APPROVED
    assert request.related_decision_log_id == decision_log.id


def test_reject_proposed_decision_log_creates_human_review_and_updates_records():
    session = make_session()
    request, decision_log = create_request_and_proposed_decision(session)

    result = review_decision_log(
        session,
        decision_log_id=decision_log.id,
        reviewer="Kaichang",
        review_decision="reject",
        comment="Insufficient context.",
    )

    session.refresh(decision_log)
    session.refresh(request)
    assert result.review_decision == "reject"
    assert result.decision_log_status == "rejected"
    assert result.decision_request_status == "rejected"
    assert decision_log.status == DecisionStatus.REJECTED
    assert decision_log.approved_by is None
    assert request.status == DecisionRequestStatus.REJECTED
    assert request.related_decision_log_id == decision_log.id
    assert list_human_reviews_for_decision_log(session, decision_log.id)[0].comment == "Insufficient context."


def test_already_approved_decision_log_cannot_be_reviewed_again():
    session = make_session()
    _, decision_log = create_request_and_proposed_decision(session)
    review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="approve")

    with pytest.raises(DecisionLogNotReviewableError):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="reject")


def test_already_rejected_decision_log_cannot_be_reviewed_again():
    session = make_session()
    _, decision_log = create_request_and_proposed_decision(session)
    review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="reject")

    with pytest.raises(DecisionLogNotReviewableError):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="approve")


def test_second_human_review_for_same_decision_log_is_rejected_at_service_level():
    session = make_session()
    request, decision_log = create_request_and_proposed_decision(session)
    existing = HumanReview(
        decision_log_id=decision_log.id,
        decision_request_id=request.id,
        reviewer="Kaichang",
        review_decision=HumanReviewDecision.APPROVE,
    )
    session.add(existing)
    session.commit()

    with pytest.raises(HumanReviewAlreadyExistsError):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer="Someone", review_decision="approve")


def test_database_unique_constraint_prevents_duplicate_human_reviews():
    session = make_session()
    request, decision_log = create_request_and_proposed_decision(session)
    session.add(
        HumanReview(
            decision_log_id=decision_log.id,
            decision_request_id=request.id,
            reviewer="Kaichang",
            review_decision=HumanReviewDecision.APPROVE,
        )
    )
    session.commit()
    session.add(
        HumanReview(
            decision_log_id=decision_log.id,
            decision_request_id=request.id,
            reviewer="Someone",
            review_decision=HumanReviewDecision.REJECT,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_decision_log_is_rejected():
    session = make_session()

    with pytest.raises(DecisionLogNotFoundError):
        review_decision_log(session, decision_log_id=999, reviewer="Kaichang", review_decision="approve")


@pytest.mark.parametrize("reviewer", [None, "", "   "])
def test_missing_empty_or_whitespace_reviewer_is_rejected_without_human_review(reviewer):
    session = make_session()
    _, decision_log = create_request_and_proposed_decision(session)

    with pytest.raises(HumanReviewValidationError):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer=reviewer, review_decision="approve")
    assert list_human_reviews(session) == []


@pytest.mark.parametrize("review_decision", [None, "", "approved", "deny", "APPROVE"])
def test_invalid_review_decision_is_rejected_without_human_review(review_decision):
    session = make_session()
    _, decision_log = create_request_and_proposed_decision(session)

    with pytest.raises(HumanReviewValidationError):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision=review_decision)
    assert list_human_reviews(session) == []


@pytest.mark.parametrize("related_request_id", [None, "", "abc", "request-1", "0", "-1"])
def test_malformed_related_request_id_is_rejected_without_partial_update(related_request_id):
    session = make_session()
    _, decision_log = create_request_and_proposed_decision(session)
    decision_log.related_request_id = related_request_id
    session.commit()

    with pytest.raises(RelatedDecisionRequestMalformedError):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="approve")
    session.refresh(decision_log)
    assert decision_log.status == DecisionStatus.PROPOSED
    assert list_human_reviews(session) == []


def test_missing_related_decision_request_causes_clear_error_and_no_partial_human_review():
    session = make_session()
    request, decision_log = create_request_and_proposed_decision(session)
    session.delete(request)
    session.commit()

    with pytest.raises(RelatedDecisionRequestMissingError):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="approve")
    session.refresh(decision_log)
    assert decision_log.status == DecisionStatus.PROPOSED
    assert list_human_reviews(session) == []


def test_forced_failure_rolls_back_human_review_decision_log_and_decision_request(monkeypatch):
    session = make_session()
    request, decision_log = create_request_and_proposed_decision(session)

    def fail_flush():
        raise RuntimeError("forced transaction failure")

    monkeypatch.setattr(session, "flush", fail_flush)

    with pytest.raises(RuntimeError, match="forced transaction failure"):
        review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="approve")

    unchanged_decision_log = session.get(DecisionLog, decision_log.id)
    unchanged_request = session.get(DecisionRequest, request.id)
    assert list_human_reviews(session) == []
    assert unchanged_decision_log.status == DecisionStatus.PROPOSED
    assert unchanged_decision_log.approved_by is None
    assert unchanged_request.status == DecisionRequestStatus.SUBMITTED
    assert unchanged_request.related_decision_log_id is None


def test_review_service_does_not_use_independent_commit_helpers(monkeypatch):
    session = make_session()
    _, decision_log = create_request_and_proposed_decision(session)

    def fail_if_helper_commits(*args, **kwargs):
        raise AssertionError("HumanReview service must not call helper functions that commit independently")

    monkeypatch.setattr("shared.services.decision_request_service.update_decision_request_status", fail_if_helper_commits)
    monkeypatch.setattr("shared.services.knowledge_service.create_decision_log", fail_if_helper_commits)

    result = review_decision_log(session, decision_log_id=decision_log.id, reviewer="Kaichang", review_decision="approve")

    assert result.decision_log_status == "approved"
