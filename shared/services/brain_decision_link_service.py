from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from shared.models.brain_review import BrainReview
from shared.models.decision_request import DecisionRequest
from shared.models.knowledge import DecisionLog, DecisionStatus


class BrainDecisionLinkError(Exception):
    pass


class BrainReviewNotFoundError(BrainDecisionLinkError):
    pass


class BrainReviewDecisionRequestMissingError(BrainDecisionLinkError):
    pass


class BrainReviewDecisionLogLinkStaleError(BrainDecisionLinkError):
    pass


@dataclass(frozen=True)
class DecisionLogDraftResult:
    brain_review_id: int
    decision_log_id: int
    decision_log_status: str
    created: bool


def create_decision_log_draft_from_brain_review(
    session: Session,
    *,
    brain_review_id: int,
    proposed_by: str | None = None,
) -> DecisionLogDraftResult:
    brain_review = session.get(BrainReview, brain_review_id)
    if brain_review is None:
        raise BrainReviewNotFoundError(f"Unknown brain_review_id: {brain_review_id}")

    decision_request = session.get(DecisionRequest, brain_review.decision_request_id)
    if decision_request is None:
        raise BrainReviewDecisionRequestMissingError(
            f"BrainReview {brain_review_id} references missing DecisionRequest {brain_review.decision_request_id}"
        )

    if brain_review.proposed_decision_log_id is not None:
        decision_log = session.get(DecisionLog, brain_review.proposed_decision_log_id)
        if decision_log is None:
            raise BrainReviewDecisionLogLinkStaleError(
                f"BrainReview {brain_review_id} references missing DecisionLog {brain_review.proposed_decision_log_id}"
            )
        return DecisionLogDraftResult(
            brain_review_id=brain_review.id,
            decision_log_id=decision_log.id,
            decision_log_status=decision_log.status.value,
            created=False,
        )

    decision_log = DecisionLog(
        title=decision_request.question,
        decision=brain_review.recommendation.value,
        rationale=brain_review.rationale,
        proposed_by=proposed_by or brain_review.created_by,
        reviewed_by=brain_review.created_by,
        approved_by=None,
        status=DecisionStatus.PROPOSED,
        related_request_id=str(decision_request.id),
    )
    session.add(decision_log)
    session.flush()
    brain_review.proposed_decision_log_id = decision_log.id
    session.commit()
    session.refresh(brain_review)
    session.refresh(decision_log)
    return DecisionLogDraftResult(
        brain_review_id=brain_review.id,
        decision_log_id=decision_log.id,
        decision_log_status=decision_log.status.value,
        created=True,
    )

