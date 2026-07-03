from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import Base
from shared.models.knowledge import enum_values


class TriageRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TriageRecommendation(str, Enum):
    HANDLE_LOCALLY = "handle_locally"
    USE_WORKER_MODEL = "use_worker_model"
    ESCALATE_TO_BRAIN = "escalate_to_brain"
    REJECT_REQUEST = "reject_request"


class TriageResult(Base):
    __tablename__ = "triage_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_request_id: Mapped[int] = mapped_column(
        ForeignKey("decision_requests.id", ondelete="CASCADE"),
        index=True,
    )
    risk_level: Mapped[TriageRiskLevel] = mapped_column(
        SAEnum(TriageRiskLevel, values_callable=enum_values, name="triage_risk_level")
    )
    recommendation: Mapped[TriageRecommendation] = mapped_column(
        SAEnum(TriageRecommendation, values_callable=enum_values, name="triage_recommendation")
    )
    rationale: Mapped[str] = mapped_column(Text)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

