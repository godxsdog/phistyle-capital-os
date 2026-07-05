from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import Base
from shared.models.knowledge import enum_values


class BrainReviewRecommendation(str, Enum):
    PROCEED = "proceed"
    REQUEST_MORE_CONTEXT = "request_more_context"
    REJECT = "reject"
    DEFER = "defer"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class BrainReviewConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BrainReview(Base):
    __tablename__ = "brain_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_request_id: Mapped[int] = mapped_column(
        ForeignKey("decision_requests.id", ondelete="CASCADE"),
        index=True,
    )
    triage_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("triage_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation: Mapped[BrainReviewRecommendation] = mapped_column(
        SAEnum(BrainReviewRecommendation, values_callable=enum_values, name="brain_review_recommendation")
    )
    rationale: Mapped[str] = mapped_column(Text)
    confidence: Mapped[BrainReviewConfidence] = mapped_column(
        SAEnum(BrainReviewConfidence, values_callable=enum_values, name="brain_review_confidence")
    )
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    llm_backed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    llm_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_floor_applied: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    proposed_decision_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_log.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
