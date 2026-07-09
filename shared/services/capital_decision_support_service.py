from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from phistyle_platform.runtime.context import AgentRunContext
from phistyle_platform.runtime.runtime import BrainOrchestrator, TriageAgent
from shared.models.brain_review import BrainReview
from shared.models.decision_request import (
    DecisionRequest,
    DecisionRequestRiskLevel,
    DecisionRequestStatus,
    DecisionRequestType,
)
from shared.models.human_review import HumanReview
from shared.models.knowledge import DecisionLog
from shared.models.triage import TriageResult
from shared.services.brain_decision_link_service import create_decision_log_draft_from_brain_review
from shared.services.brain_review_service import create_brain_review
from shared.services.decision_request_service import create_decision_request
from shared.services.triage_service import create_triage_result


CAPITAL_APP_ID = "capital"
CAPITAL_DECISION_TYPE = "investment"
CAPITAL_INITIAL_STATUS = "submitted"


class CapitalDecisionSupportError(Exception):
    pass


class CapitalDecisionValidationError(CapitalDecisionSupportError):
    pass


class CapitalDecisionRequestNotFoundError(CapitalDecisionSupportError):
    pass


class CapitalDecisionRequestScopeError(CapitalDecisionSupportError):
    pass


class CapitalDecisionRelatedRecordError(CapitalDecisionSupportError):
    pass


@dataclass(frozen=True)
class CapitalPipelineResult:
    decision_request_id: int
    decision_request_status: str
    triage_result_id: int
    triage_recommendation: str
    brain_review_id: int
    brain_recommendation: str
    decision_log_id: int
    decision_log_status: str
    decision_log_approved_by: str | None
    requires_human_review: bool


@dataclass(frozen=True)
class CapitalDecisionSummary:
    decision_request: DecisionRequest
    triage_result: TriageResult | None
    brain_review: BrainReview | None
    decision_log: DecisionLog | None
    human_review: HumanReview | None
    requires_human_review: bool


def create_capital_decision_request(
    session: Session,
    *,
    question: str | None,
    context: str | None,
    options: str | None,
    risk_level: str,
    created_by: str | None,
    commit: bool = True,
) -> DecisionRequest:
    normalized_question = _required_trimmed(question, "question")
    normalized_context = _required_trimmed(context, "context")
    normalized_options = _required_trimmed(options, "options")
    normalized_created_by = _required_trimmed(created_by, "created_by")
    normalized_risk_level = _normalize_risk_level(risk_level)
    return create_decision_request(
        session,
        app_id=CAPITAL_APP_ID,
        decision_type=CAPITAL_DECISION_TYPE,
        question=normalized_question,
        context=normalized_context,
        options=normalized_options,
        risk_level=normalized_risk_level,
        status=CAPITAL_INITIAL_STATUS,
        created_by=normalized_created_by,
        commit=commit,
    )


def run_capital_decision_pipeline(
    session: Session,
    *,
    decision_request_id: int,
) -> CapitalPipelineResult:
    decision_request = _get_capital_decision_request(session, decision_request_id)
    triage_result = _latest_triage_result(session, decision_request.id)
    if triage_result is None:
        triage_result = _run_and_persist_triage(session, decision_request)
    _progress_status(session, decision_request, DecisionRequestStatus.SUBMITTED, DecisionRequestStatus.TRIAGED)

    brain_review = _latest_brain_review(session, decision_request.id)
    if brain_review is None:
        brain_review = _run_and_persist_brain_review(session, decision_request, triage_result)
    _progress_status(session, decision_request, DecisionRequestStatus.TRIAGED, DecisionRequestStatus.BRAIN_REVIEWED)

    decision_log = _linked_decision_log(session, brain_review)
    if decision_log is None:
        draft_result = create_decision_log_draft_from_brain_review(
            session,
            brain_review_id=brain_review.id,
            proposed_by=brain_review.created_by,
        )
        decision_log = session.get(DecisionLog, draft_result.decision_log_id)
        if decision_log is None:
            raise CapitalDecisionSupportError(f"DecisionLog {draft_result.decision_log_id} was not found after draft creation")
    _validate_decision_log_related_request(session, decision_log, decision_request.id)

    human_review = _human_review_for_decision_log(session, decision_log.id)
    session.refresh(decision_request)
    session.refresh(decision_log)
    return CapitalPipelineResult(
        decision_request_id=decision_request.id,
        decision_request_status=decision_request.status.value,
        triage_result_id=triage_result.id,
        triage_recommendation=triage_result.recommendation.value,
        brain_review_id=brain_review.id,
        brain_recommendation=brain_review.recommendation.value,
        decision_log_id=decision_log.id,
        decision_log_status=decision_log.status.value,
        decision_log_approved_by=decision_log.approved_by,
        requires_human_review=human_review is None,
    )


def get_capital_decision_summary(
    session: Session,
    *,
    decision_request_id: int,
) -> CapitalDecisionSummary:
    decision_request = _get_capital_decision_request(session, decision_request_id)
    triage_result = _latest_triage_result(session, decision_request.id)
    brain_review = _latest_brain_review(session, decision_request.id)
    decision_log = _linked_decision_log(session, brain_review) if brain_review is not None else None
    if decision_log is not None:
        _validate_decision_log_related_request(session, decision_log, decision_request.id)
    human_review = _human_review_for_decision_log(session, decision_log.id) if decision_log is not None else None
    return CapitalDecisionSummary(
        decision_request=decision_request,
        triage_result=triage_result,
        brain_review=brain_review,
        decision_log=decision_log,
        human_review=human_review,
        requires_human_review=decision_log is not None and human_review is None,
    )


def list_capital_decision_requests(session: Session) -> list[DecisionRequest]:
    return list(
        session.scalars(
            select(DecisionRequest)
            .where(
                DecisionRequest.app_id == CAPITAL_APP_ID,
                DecisionRequest.decision_type == DecisionRequestType.INVESTMENT,
            )
            .order_by(DecisionRequest.id)
        )
    )


def _get_capital_decision_request(session: Session, decision_request_id: int) -> DecisionRequest:
    decision_request = session.get(DecisionRequest, decision_request_id)
    if decision_request is None:
        raise CapitalDecisionRequestNotFoundError(f"Unknown decision_request_id: {decision_request_id}")
    if decision_request.app_id != CAPITAL_APP_ID or decision_request.decision_type != DecisionRequestType.INVESTMENT:
        raise CapitalDecisionRequestScopeError(
            f"DecisionRequest {decision_request_id} is not a Capital investment decision"
        )
    return decision_request


def _run_and_persist_triage(session: Session, decision_request: DecisionRequest) -> TriageResult:
    result = TriageAgent().run(
        {
            "decision_request_id": decision_request.id,
            "question": decision_request.question,
            "context": decision_request.context,
            "decision_type": decision_request.decision_type.value,
            "risk_level": decision_request.risk_level.value,
        },
        AgentRunContext(run_id=f"capital-triage-{decision_request.id}"),
    )
    return create_triage_result(
        session,
        decision_request_id=decision_request.id,
        risk_level=result.output["risk_level"],
        recommendation=result.output["recommendation"],
        rationale=result.output["rationale"],
        flags=result.output["flags"],
        created_by="triage-agent",
    )


def _run_and_persist_brain_review(
    session: Session,
    decision_request: DecisionRequest,
    triage_result: TriageResult,
) -> BrainReview:
    result = BrainOrchestrator().run(
        {
            "decision_request_id": decision_request.id,
            "triage_result_id": triage_result.id,
            "question": decision_request.question,
            "context": decision_request.context,
            "risk_level": decision_request.risk_level.value,
            "triage_recommendation": triage_result.recommendation.value,
        },
        AgentRunContext(run_id=f"capital-brain-{decision_request.id}"),
    )
    return create_brain_review(
        session,
        decision_request_id=decision_request.id,
        triage_result_id=result.output["triage_result_id"],
        recommendation=result.output["recommendation"],
        rationale=result.output["rationale"],
        confidence=result.output["confidence"],
        risks=result.output["risks"],
        required_human_approval=result.output["required_human_approval"],
        proposed_decision_log_id=None,
        llm_backed=result.output["llm_backed"],
        llm_provider=result.output["llm_provider"],
        llm_model=result.output["llm_model"],
        llm_fallback_reason=result.output["llm_fallback_reason"],
        llm_floor_applied=result.output["llm_floor_applied"],
        created_by="brain-orchestrator",
    )


def _progress_status(
    session: Session,
    decision_request: DecisionRequest,
    current_status: DecisionRequestStatus,
    next_status: DecisionRequestStatus,
) -> None:
    session.refresh(decision_request)
    if decision_request.status == current_status:
        decision_request.status = next_status
        session.commit()
        session.refresh(decision_request)


def _latest_triage_result(session: Session, decision_request_id: int) -> TriageResult | None:
    return session.scalars(
        select(TriageResult)
        .where(TriageResult.decision_request_id == decision_request_id)
        .order_by(TriageResult.created_at.desc(), TriageResult.id.desc())
    ).first()


def _latest_brain_review(session: Session, decision_request_id: int) -> BrainReview | None:
    return session.scalars(
        select(BrainReview)
        .where(BrainReview.decision_request_id == decision_request_id)
        .order_by(BrainReview.created_at.desc(), BrainReview.id.desc())
    ).first()


def _linked_decision_log(session: Session, brain_review: BrainReview) -> DecisionLog | None:
    if brain_review.proposed_decision_log_id is None:
        return None
    return session.get(DecisionLog, brain_review.proposed_decision_log_id)


def _human_review_for_decision_log(session: Session, decision_log_id: int) -> HumanReview | None:
    return session.scalars(
        select(HumanReview)
        .where(HumanReview.decision_log_id == decision_log_id)
        .order_by(HumanReview.created_at.desc(), HumanReview.id.desc())
    ).first()


def _validate_decision_log_related_request(
    session: Session,
    decision_log: DecisionLog,
    expected_decision_request_id: int,
) -> None:
    if decision_log.related_request_id is None:
        raise CapitalDecisionRelatedRecordError(f"DecisionLog {decision_log.id} is missing related_request_id")
    try:
        related_request_id = int(decision_log.related_request_id)
    except ValueError as exc:
        raise CapitalDecisionRelatedRecordError(
            f"DecisionLog {decision_log.id} has malformed related_request_id: {decision_log.related_request_id}"
        ) from exc
    if related_request_id != expected_decision_request_id:
        raise CapitalDecisionRelatedRecordError(
            f"DecisionLog {decision_log.id} is linked to DecisionRequest {related_request_id}, expected {expected_decision_request_id}"
        )
    if session.get(DecisionRequest, related_request_id) is None:
        raise CapitalDecisionRelatedRecordError(
            f"DecisionLog {decision_log.id} references missing DecisionRequest {related_request_id}"
        )


def _required_trimmed(value: str | None, field_name: str) -> str:
    if value is None:
        raise CapitalDecisionValidationError(f"{field_name} is required")
    normalized = value.strip()
    if not normalized:
        raise CapitalDecisionValidationError(f"{field_name} must not be empty")
    return normalized


def _normalize_risk_level(risk_level: str) -> str:
    try:
        return DecisionRequestRiskLevel(risk_level).value
    except ValueError as exc:
        raise CapitalDecisionValidationError("risk_level must be low, medium, or high") from exc
