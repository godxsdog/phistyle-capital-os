from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.knowledge import (
    AgentMemory,
    AgentMemoryType,
    DecisionLog,
    DecisionStatus,
    KnowledgeDocument,
    KnowledgeSourceType,
    MemoryImportance,
    StorageBackend,
)


def create_knowledge_document(
    session: Session,
    *,
    title: str,
    content: str,
    source_type: str,
    tags: str | None = None,
    storage_backend: str,
    file_path: str | None = None,
) -> KnowledgeDocument:
    document = KnowledgeDocument(
        title=title,
        content=content,
        source_type=KnowledgeSourceType(source_type),
        tags=tags,
        storage_backend=StorageBackend(storage_backend),
        file_path=file_path,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def list_knowledge_documents(session: Session) -> list[KnowledgeDocument]:
    return list(session.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id)))


def get_knowledge_document(session: Session, document_id: int) -> KnowledgeDocument | None:
    return session.get(KnowledgeDocument, document_id)


def create_agent_memory(
    session: Session,
    *,
    agent_id: str,
    memory_type: str,
    content: str,
    importance: str,
) -> AgentMemory:
    memory = AgentMemory(
        agent_id=agent_id,
        memory_type=AgentMemoryType(memory_type),
        content=content,
        importance=MemoryImportance(importance),
    )
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


def list_agent_memory(session: Session) -> list[AgentMemory]:
    return list(session.scalars(select(AgentMemory).order_by(AgentMemory.id)))


def create_decision_log(
    session: Session,
    *,
    title: str,
    decision: str,
    rationale: str,
    proposed_by: str | None = None,
    reviewed_by: str | None = None,
    approved_by: str | None = None,
    status: str,
    related_request_id: str | None = None,
) -> DecisionLog:
    decision_log = DecisionLog(
        title=title,
        decision=decision,
        rationale=rationale,
        proposed_by=proposed_by,
        reviewed_by=reviewed_by,
        approved_by=approved_by,
        status=DecisionStatus(status),
        related_request_id=related_request_id,
    )
    session.add(decision_log)
    session.commit()
    session.refresh(decision_log)
    return decision_log


def list_decision_logs(session: Session) -> list[DecisionLog]:
    return list(session.scalars(select(DecisionLog).order_by(DecisionLog.id)))
