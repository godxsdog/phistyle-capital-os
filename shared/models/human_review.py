from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import Base
from shared.models.knowledge import enum_values


class HumanReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class HumanReview(Base):
    __tablename__ = "human_reviews"
    __table_args__ = (UniqueConstraint("decision_log_id", name="uq_human_reviews_decision_log_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_log_id: Mapped[int] = mapped_column(
        ForeignKey("decision_log.id", ondelete="CASCADE"),
        index=True,
    )
    decision_request_id: Mapped[int] = mapped_column(
        ForeignKey("decision_requests.id", ondelete="CASCADE"),
        index=True,
    )
    brain_review_id: Mapped[int | None] = mapped_column(
        ForeignKey("brain_reviews.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    review_decision: Mapped[HumanReviewDecision] = mapped_column(
        SAEnum(HumanReviewDecision, values_callable=enum_values, name="human_review_decision")
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
