from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import Base
from shared.models.knowledge import enum_values


class DecisionRequestType(str, Enum):
    INVESTMENT = "investment"
    TRAVEL = "travel"
    CREDIT_CARD = "credit_card"
    MEDICAL = "medical"
    ENGINEERING = "engineering"
    PERSONAL = "personal"
    ARCHITECTURE = "architecture"


class DecisionRequestRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DecisionRequestStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    TRIAGED = "triaged"
    BRAIN_REVIEWED = "brain_reviewed"
    HUMAN_APPROVED = "human_approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class DecisionRequest(Base):
    __tablename__ = "decision_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[str] = mapped_column(String(120), index=True)
    decision_type: Mapped[DecisionRequestType] = mapped_column(
        SAEnum(DecisionRequestType, values_callable=enum_values, name="decision_request_type")
    )
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[DecisionRequestRiskLevel] = mapped_column(
        SAEnum(DecisionRequestRiskLevel, values_callable=enum_values, name="decision_request_risk_level")
    )
    status: Mapped[DecisionRequestStatus] = mapped_column(
        SAEnum(DecisionRequestStatus, values_callable=enum_values, name="decision_request_status")
    )
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    related_knowledge_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_decision_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_log.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

