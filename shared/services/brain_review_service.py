from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.brain_review import (
    BrainReview,
    BrainReviewConfidence,
    BrainReviewRecommendation,
)


def create_brain_review(
    session: Session,
    *,
    decision_request_id: int,
    recommendation: str,
    rationale: str,
    confidence: str,
    created_by: str,
    triage_result_id: int | None = None,
    risks: list[str] | str | None = None,
    required_human_approval: bool = True,
    proposed_decision_log_id: int | None = None,
) -> BrainReview:
    brain_review = BrainReview(
        decision_request_id=decision_request_id,
        triage_result_id=triage_result_id,
        recommendation=BrainReviewRecommendation(recommendation),
        rationale=rationale,
        confidence=BrainReviewConfidence(confidence),
        risks=_serialize_risks(risks),
        required_human_approval=required_human_approval,
        proposed_decision_log_id=proposed_decision_log_id,
        created_by=created_by,
    )
    session.add(brain_review)
    session.commit()
    session.refresh(brain_review)
    return brain_review


def list_brain_reviews(session: Session) -> list[BrainReview]:
    return list(session.scalars(select(BrainReview).order_by(BrainReview.id)))


def list_brain_reviews_for_request(session: Session, decision_request_id: int) -> list[BrainReview]:
    return list(
        session.scalars(
            select(BrainReview)
            .where(BrainReview.decision_request_id == decision_request_id)
            .order_by(BrainReview.id)
        )
    )


def get_latest_brain_review_for_request(
    session: Session,
    decision_request_id: int,
) -> BrainReview | None:
    return session.scalars(
        select(BrainReview)
        .where(BrainReview.decision_request_id == decision_request_id)
        .order_by(BrainReview.id.desc())
    ).first()


def _serialize_risks(risks: list[str] | str | None) -> str:
    if risks is None:
        return ""
    if isinstance(risks, str):
        return risks
    for risk in risks:
        if "," in risk:
            raise ValueError("Brain review risk values must not contain commas")
    return ",".join(risks)

