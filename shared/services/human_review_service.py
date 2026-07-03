from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.brain_review import BrainReview
from shared.models.decision_request import DecisionRequest, DecisionRequestStatus
from shared.models.human_review import HumanReview, HumanReviewDecision
from shared.models.knowledge import DecisionLog, DecisionStatus


class HumanReviewError(Exception):
    pass


class HumanReviewValidationError(HumanReviewError):
    pass


class DecisionLogNotFoundError(HumanReviewError):
    pass


class DecisionLogNotReviewableError(HumanReviewError):
    pass


class HumanReviewAlreadyExistsError(HumanReviewError):
    pass


class RelatedDecisionRequestMalformedError(HumanReviewError):
    pass


class RelatedDecisionRequestMissingError(HumanReviewError):
    pass


@dataclass(frozen=True)
class HumanReviewResult:
    human_review_id: int
    decision_log_id: int
    decision_log_status: str
    decision_request_id: int
    decision_request_status: str
    review_decision: str


def review_decision_log(
    session: Session,
    *,
    decision_log_id: int,
    reviewer: str | None,
    review_decision: str | None,
    comment: str | None = None,
) -> HumanReviewResult:
    normalized_reviewer = _normalize_reviewer(reviewer)
    normalized_decision = _normalize_review_decision(review_decision)

    decision_log = session.get(DecisionLog, decision_log_id)
    if decision_log is None:
        raise DecisionLogNotFoundError(f"Unknown decision_log_id: {decision_log_id}")
    if decision_log.status != DecisionStatus.PROPOSED:
        raise DecisionLogNotReviewableError(
            f"DecisionLog {decision_log_id} is not proposed and cannot be reviewed"
        )
    if _human_review_exists(session, decision_log_id):
        raise HumanReviewAlreadyExistsError(f"DecisionLog {decision_log_id} already has a HumanReview")

    decision_request_id = _parse_related_request_id(decision_log.related_request_id)
    decision_request = session.get(DecisionRequest, decision_request_id)
    if decision_request is None:
        raise RelatedDecisionRequestMissingError(
            f"DecisionLog {decision_log_id} references missing DecisionRequest {decision_request_id}"
        )

    brain_review = session.scalar(
        select(BrainReview).where(BrainReview.proposed_decision_log_id == decision_log.id).order_by(BrainReview.id)
    )
    human_review = HumanReview(
        decision_log_id=decision_log.id,
        decision_request_id=decision_request.id,
        brain_review_id=brain_review.id if brain_review is not None else None,
        reviewer=normalized_reviewer,
        review_decision=normalized_decision,
        comment=comment,
    )

    if normalized_decision == HumanReviewDecision.APPROVE:
        decision_log.status = DecisionStatus.APPROVED
        decision_log.approved_by = normalized_reviewer
        decision_request.status = DecisionRequestStatus.HUMAN_APPROVED
    else:
        decision_log.status = DecisionStatus.REJECTED
        decision_log.approved_by = None
        decision_request.status = DecisionRequestStatus.REJECTED
    decision_request.related_decision_log_id = decision_log.id

    try:
        session.add(human_review)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(human_review)
    session.refresh(decision_log)
    session.refresh(decision_request)
    return HumanReviewResult(
        human_review_id=human_review.id,
        decision_log_id=decision_log.id,
        decision_log_status=decision_log.status.value,
        decision_request_id=decision_request.id,
        decision_request_status=decision_request.status.value,
        review_decision=human_review.review_decision.value,
    )


def list_human_reviews(session: Session) -> list[HumanReview]:
    return list(session.scalars(select(HumanReview).order_by(HumanReview.id)))


def list_human_reviews_for_decision_log(session: Session, decision_log_id: int) -> list[HumanReview]:
    return list(
        session.scalars(
            select(HumanReview).where(HumanReview.decision_log_id == decision_log_id).order_by(HumanReview.id)
        )
    )


def _normalize_reviewer(reviewer: str | None) -> str:
    if reviewer is None:
        raise HumanReviewValidationError("reviewer is required")
    normalized = reviewer.strip()
    if not normalized:
        raise HumanReviewValidationError("reviewer must not be empty")
    return normalized


def _normalize_review_decision(review_decision: str | None) -> HumanReviewDecision:
    if review_decision is None:
        raise HumanReviewValidationError("review_decision is required")
    if review_decision not in {HumanReviewDecision.APPROVE.value, HumanReviewDecision.REJECT.value}:
        raise HumanReviewValidationError("review_decision must be exactly 'approve' or 'reject'")
    return HumanReviewDecision(review_decision)


def _human_review_exists(session: Session, decision_log_id: int) -> bool:
    return (
        session.scalar(select(HumanReview.id).where(HumanReview.decision_log_id == decision_log_id).limit(1))
        is not None
    )


def _parse_related_request_id(related_request_id: str | None) -> int:
    if related_request_id is None:
        raise RelatedDecisionRequestMalformedError("DecisionLog.related_request_id is missing")
    try:
        decision_request_id = int(related_request_id)
    except ValueError as exc:
        raise RelatedDecisionRequestMalformedError(
            f"DecisionLog.related_request_id is malformed: {related_request_id}"
        ) from exc
    if decision_request_id <= 0:
        raise RelatedDecisionRequestMalformedError(
            f"DecisionLog.related_request_id is malformed: {related_request_id}"
        )
    return decision_request_id
