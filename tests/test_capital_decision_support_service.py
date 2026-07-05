from datetime import datetime, timedelta
import json

import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.llm_router.types import LLMResponse
from shared.database.base import Base
from shared.models import brain_review, decision_request, human_review, knowledge, triage  # noqa: F401
from shared.models.brain_review import BrainReview
from shared.models.decision_request import DecisionRequestStatus
from shared.models.knowledge import DecisionLog, DecisionStatus
from shared.models.triage import TriageResult
from shared.services.brain_decision_link_service import BrainReviewDecisionLogLinkStaleError
from shared.services.brain_review_service import create_brain_review
from shared.services.capital_decision_support_service import (
    CapitalDecisionRelatedRecordError,
    CapitalDecisionRequestScopeError,
    CapitalDecisionValidationError,
    create_capital_decision_request,
    get_capital_decision_summary,
    list_capital_decision_requests,
    run_capital_decision_pipeline,
)
from shared.services.decision_request_service import create_decision_request
from shared.services.human_review_service import list_human_reviews, review_decision_log
from shared.services.knowledge_service import create_decision_log
from shared.services.triage_service import create_triage_result


@pytest.fixture(autouse=True)
def default_deepseek_dry_run(monkeypatch):
    def mock_chat(self, request):
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content="[dry-run:deepseek] missing api key",
            dry_run=True,
            metadata={},
        )

    monkeypatch.setattr("phistyle_platform.runtime.runtime.DeepSeekProvider.chat", mock_chat)


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


def create_capital_request(session, **overrides):
    payload = {
        "question": "  Should I reduce AVGO exposure?  ",
        "context": "  AVGO is now concentrated in the portfolio.  ",
        "options": "  hold | reduce 20% | hedge  ",
        "risk_level": "high",
        "created_by": "  Kaichang  ",
    }
    payload.update(overrides)
    return create_capital_decision_request(session, **payload)


def valid_brain_review_response(**overrides):
    payload = {
        "recommendation": "human_review_required",
        "rationale": "LLM review questions the thesis and flags missing evidence.",
        "confidence": "high",
        "risks": ["missing-evidence"],
    }
    payload.update(overrides)
    return LLMResponse(
        provider_id="deepseek",
        model="deepseek-reasoner",
        content=json.dumps(payload),
        dry_run=False,
        metadata={},
    )


def test_create_capital_decision_request_owns_and_normalizes_fields():
    session = make_session()

    request = create_capital_request(session)

    assert request.app_id == "capital"
    assert request.decision_type.value == "investment"
    assert request.status.value == "submitted"
    assert request.question == "Should I reduce AVGO exposure?"
    assert request.context == "AVGO is now concentrated in the portfolio."
    assert request.options == "hold | reduce 20% | hedge"
    assert request.created_by == "Kaichang"


@pytest.mark.parametrize("field", ["question", "context", "options", "created_by"])
def test_capital_decision_required_text_fields_reject_empty_values(field):
    session = make_session()

    with pytest.raises(CapitalDecisionValidationError):
        create_capital_request(session, **{field: "   "})


def test_capital_decision_invalid_risk_level_rejected():
    session = make_session()

    with pytest.raises(CapitalDecisionValidationError):
        create_capital_request(session, risk_level="urgent")


def test_pipeline_rejects_non_capital_decision_request():
    session = make_session()
    request = create_decision_request(
        session,
        app_id="travel",
        decision_type="travel",
        question="Book a hotel?",
        context="Planning a trip.",
        risk_level="medium",
        status="submitted",
    )

    with pytest.raises(CapitalDecisionRequestScopeError):
        run_capital_decision_pipeline(session, decision_request_id=request.id)


def test_first_pipeline_run_creates_records_and_stops_before_human_review(monkeypatch):
    session = make_session()
    request = create_capital_request(session)

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("Capital pipeline must not call LLM providers")

    def fail_if_human_review_runs(*args, **kwargs):
        raise AssertionError("Capital pipeline must not call HumanReview")

    monkeypatch.setattr("services.llm_router.providers.deepseek.DeepSeekProvider.chat", fail_if_llm_runs)
    monkeypatch.setattr("shared.services.human_review_service.review_decision_log", fail_if_human_review_runs)

    result = run_capital_decision_pipeline(session, decision_request_id=request.id)

    session.refresh(request)
    decision_log = session.get(DecisionLog, result.decision_log_id)
    assert result.decision_request_status == "brain_reviewed"
    assert result.triage_recommendation == "escalate_to_brain"
    assert result.brain_recommendation == "human_review_required"
    assert result.decision_log_status == "proposed"
    assert result.decision_log_approved_by is None
    assert result.requires_human_review is True
    assert request.status == DecisionRequestStatus.BRAIN_REVIEWED
    assert decision_log.status == DecisionStatus.PROPOSED
    assert decision_log.approved_by is None
    assert session.query(TriageResult).count() == 1
    assert session.query(BrainReview).count() == 1
    assert session.query(DecisionLog).count() == 1
    assert list_human_reviews(session) == []


def test_second_pipeline_run_reuses_triage_brain_and_decision_log():
    session = make_session()
    request = create_capital_request(session)

    first = run_capital_decision_pipeline(session, decision_request_id=request.id)
    second = run_capital_decision_pipeline(session, decision_request_id=request.id)

    assert second.triage_result_id == first.triage_result_id
    assert second.brain_review_id == first.brain_review_id
    assert second.decision_log_id == first.decision_log_id
    assert session.query(TriageResult).count() == 1
    assert session.query(BrainReview).count() == 1
    assert session.query(DecisionLog).count() == 1


def test_pipeline_persists_llm_metadata_and_reuses_existing_brain_review(monkeypatch):
    session = make_session()
    request = create_capital_request(
        session,
        context="INFORMATIONAL ONLY review of portfolio concentration.",
        risk_level="low",
    )
    call_count = 0

    def mock_chat(self, request):
        nonlocal call_count
        call_count += 1
        return valid_brain_review_response(recommendation="defer")

    monkeypatch.setattr("phistyle_platform.runtime.runtime.DeepSeekProvider.chat", mock_chat)

    first = run_capital_decision_pipeline(session, decision_request_id=request.id)
    second = run_capital_decision_pipeline(session, decision_request_id=request.id)
    review = session.get(BrainReview, first.brain_review_id)

    assert second.brain_review_id == first.brain_review_id
    assert call_count == 1
    assert review.recommendation.value == "defer"
    assert review.rationale == "LLM review questions the thesis and flags missing evidence."
    assert review.confidence.value == "high"
    assert review.llm_backed is True
    assert review.llm_provider == "deepseek"
    assert review.llm_model == "deepseek-reasoner"
    assert review.llm_fallback_reason is None
    assert review.llm_floor_applied is False


def test_pipeline_sanitizes_comma_containing_llm_risks_before_storage(monkeypatch):
    session = make_session()
    request = create_capital_request(
        session,
        context="INFORMATIONAL ONLY review of portfolio concentration.",
        risk_level="low",
    )

    def mock_chat(self, request):
        return valid_brain_review_response(
            recommendation="defer",
            risks=["position size, liquidity", "missing-evidence"],
        )

    monkeypatch.setattr("phistyle_platform.runtime.runtime.DeepSeekProvider.chat", mock_chat)

    result = run_capital_decision_pipeline(session, decision_request_id=request.id)
    review = session.get(BrainReview, result.brain_review_id)

    assert review.recommendation.value == "defer"
    assert review.risks == "position size; liquidity,missing-evidence"
    assert review.llm_backed is True


def test_orphaned_proposed_decision_log_id_is_not_silently_repaired():
    session = make_session()
    request = create_capital_request(session)
    triage_result = create_triage_result(
        session,
        decision_request_id=request.id,
        risk_level="high",
        recommendation="escalate_to_brain",
        rationale="High risk.",
        created_by="triage-agent",
    )
    create_brain_review(
        session,
        decision_request_id=request.id,
        triage_result_id=triage_result.id,
        recommendation="human_review_required",
        rationale="Needs review.",
        confidence="medium",
        created_by="brain-orchestrator",
        proposed_decision_log_id=999,
    )

    with pytest.raises(BrainReviewDecisionLogLinkStaleError):
        run_capital_decision_pipeline(session, decision_request_id=request.id)
    assert session.query(DecisionLog).count() == 0


def test_malformed_related_request_id_returns_clear_error():
    session = make_session()
    request = create_capital_request(session)
    result = run_capital_decision_pipeline(session, decision_request_id=request.id)
    decision_log = session.get(DecisionLog, result.decision_log_id)
    decision_log.related_request_id = "request-1"
    session.commit()

    with pytest.raises(CapitalDecisionRelatedRecordError):
        run_capital_decision_pipeline(session, decision_request_id=request.id)


def test_pipeline_after_approve_preserves_final_status_and_approved_by():
    session = make_session()
    request = create_capital_request(session)
    first = run_capital_decision_pipeline(session, decision_request_id=request.id)
    review_decision_log(
        session,
        decision_log_id=first.decision_log_id,
        reviewer="Kaichang",
        review_decision="approve",
    )

    second = run_capital_decision_pipeline(session, decision_request_id=request.id)
    decision_log = session.get(DecisionLog, second.decision_log_id)
    session.refresh(request)

    assert second.decision_request_status == "human_approved"
    assert second.decision_log_status == "approved"
    assert second.decision_log_approved_by == "Kaichang"
    assert second.requires_human_review is False
    assert request.status == DecisionRequestStatus.HUMAN_APPROVED
    assert decision_log.status == DecisionStatus.APPROVED
    assert decision_log.approved_by == "Kaichang"


def test_pipeline_after_reject_preserves_final_status_and_null_approved_by():
    session = make_session()
    request = create_capital_request(session)
    first = run_capital_decision_pipeline(session, decision_request_id=request.id)
    review_decision_log(
        session,
        decision_log_id=first.decision_log_id,
        reviewer="Kaichang",
        review_decision="reject",
    )

    second = run_capital_decision_pipeline(session, decision_request_id=request.id)
    decision_log = session.get(DecisionLog, second.decision_log_id)
    session.refresh(request)

    assert second.decision_request_status == "rejected"
    assert second.decision_log_status == "rejected"
    assert second.decision_log_approved_by is None
    assert second.requires_human_review is False
    assert request.status == DecisionRequestStatus.REJECTED
    assert decision_log.status == DecisionStatus.REJECTED
    assert decision_log.approved_by is None


def test_archived_decision_request_status_is_never_downgraded():
    session = make_session()
    request = create_capital_request(session)
    request.status = DecisionRequestStatus.ARCHIVED
    session.commit()

    result = run_capital_decision_pipeline(session, decision_request_id=request.id)
    session.refresh(request)

    assert result.decision_request_status == "archived"
    assert request.status == DecisionRequestStatus.ARCHIVED


def test_latest_triage_selection_uses_created_at_then_id():
    session = make_session()
    request = create_capital_request(session)
    old = create_triage_result(
        session,
        decision_request_id=request.id,
        risk_level="low",
        recommendation="handle_locally",
        rationale="old",
        created_by="triage-agent",
    )
    latest = create_triage_result(
        session,
        decision_request_id=request.id,
        risk_level="high",
        recommendation="escalate_to_brain",
        rationale="latest",
        created_by="triage-agent",
    )
    now = datetime.utcnow()
    old.created_at = now - timedelta(days=1)
    latest.created_at = now
    session.commit()

    result = run_capital_decision_pipeline(session, decision_request_id=request.id)

    assert result.triage_result_id == latest.id
    assert result.triage_recommendation == "escalate_to_brain"


def test_latest_brain_review_selection_uses_created_at_then_id():
    session = make_session()
    request = create_capital_request(session)
    triage_result = create_triage_result(
        session,
        decision_request_id=request.id,
        risk_level="high",
        recommendation="escalate_to_brain",
        rationale="High risk.",
        created_by="triage-agent",
    )
    old = create_brain_review(
        session,
        decision_request_id=request.id,
        triage_result_id=triage_result.id,
        recommendation="defer",
        rationale="old",
        confidence="low",
        created_by="brain-orchestrator",
    )
    latest = create_brain_review(
        session,
        decision_request_id=request.id,
        triage_result_id=triage_result.id,
        recommendation="human_review_required",
        rationale="latest",
        confidence="medium",
        created_by="brain-orchestrator",
    )
    now = datetime.utcnow()
    old.created_at = now
    latest.created_at = now
    session.commit()

    result = run_capital_decision_pipeline(session, decision_request_id=request.id)

    assert result.brain_review_id == latest.id
    assert result.brain_recommendation == "human_review_required"


def test_summary_and_list_use_capital_records_only():
    session = make_session()
    capital_request = create_capital_request(session)
    create_decision_request(
        session,
        app_id="travel",
        decision_type="travel",
        question="Book a hotel?",
        context="Planning a trip.",
        risk_level="medium",
        status="submitted",
    )
    result = run_capital_decision_pipeline(session, decision_request_id=capital_request.id)

    summary = get_capital_decision_summary(session, decision_request_id=capital_request.id)
    capital_list = list_capital_decision_requests(session)

    assert [request.id for request in capital_list] == [capital_request.id]
    assert summary.decision_request.id == capital_request.id
    assert summary.triage_result.id == result.triage_result_id
    assert summary.brain_review.id == result.brain_review_id
    assert summary.decision_log.id == result.decision_log_id
    assert summary.human_review is None
    assert summary.requires_human_review is True


def test_summary_includes_human_review_after_explicit_review():
    session = make_session()
    request = create_capital_request(session)
    result = run_capital_decision_pipeline(session, decision_request_id=request.id)
    review_decision_log(session, decision_log_id=result.decision_log_id, reviewer="Kaichang", review_decision="approve")

    summary = get_capital_decision_summary(session, decision_request_id=request.id)

    assert summary.human_review is not None
    assert summary.human_review.reviewer == "Kaichang"
    assert summary.human_review.review_decision.value == "approve"
    assert summary.requires_human_review is False
