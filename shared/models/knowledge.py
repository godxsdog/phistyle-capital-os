from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import Base


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class KnowledgeSourceType(str, Enum):
    MANUAL = "manual"
    AGENT_GENERATED = "agent_generated"
    IMPORT = "import"


class StorageBackend(str, Enum):
    LOCAL = "local"
    NAS = "nas"
    EXTERNAL = "external"


class AgentMemoryType(str, Enum):
    OBSERVATION = "observation"
    SUMMARY = "summary"
    DECISION_CONTEXT = "decision_context"


class MemoryImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        SAEnum(KnowledgeSourceType, values_callable=enum_values, name="knowledge_source_type")
    )
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_backend: Mapped[StorageBackend] = mapped_column(
        SAEnum(StorageBackend, values_callable=enum_values, name="storage_backend")
    )
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(120), index=True)
    memory_type: Mapped[AgentMemoryType] = mapped_column(
        SAEnum(AgentMemoryType, values_callable=enum_values, name="agent_memory_type")
    )
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[MemoryImportance] = mapped_column(
        SAEnum(MemoryImportance, values_callable=enum_values, name="memory_importance")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionLog(Base):
    __tablename__ = "decision_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    decision: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    proposed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[DecisionStatus] = mapped_column(
        SAEnum(DecisionStatus, values_callable=enum_values, name="decision_status")
    )
    related_request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

