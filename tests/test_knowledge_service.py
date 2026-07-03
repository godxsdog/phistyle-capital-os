import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import knowledge  # noqa: F401
from shared.services.knowledge_service import (
    create_agent_memory,
    create_decision_log,
    create_knowledge_document,
    list_agent_memory,
    list_decision_logs,
    list_knowledge_documents,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_create_and_list_knowledge_document():
    session = make_session()

    create_knowledge_document(
        session,
        title="AI infrastructure note",
        content="Short summary only.",
        source_type="manual",
        tags="ai,infra",
        storage_backend="local",
    )

    documents = list_knowledge_documents(session)
    assert len(documents) == 1
    assert documents[0].title == "AI infrastructure note"
    assert documents[0].source_type.value == "manual"
    assert documents[0].storage_backend.value == "local"


def test_create_and_list_knowledge_document_with_nas_reference_without_file_check():
    session = make_session()

    create_knowledge_document(
        session,
        title="NAS reference",
        content="Booking summary.",
        source_type="import",
        tags="travel,nas",
        storage_backend="nas",
        file_path="/Volumes/PhiStyleOS/travel/missing-file.pdf",
    )

    documents = list_knowledge_documents(session)
    assert len(documents) == 1
    assert documents[0].storage_backend.value == "nas"
    assert documents[0].file_path == "/Volumes/PhiStyleOS/travel/missing-file.pdf"


def test_create_and_list_agent_memory():
    session = make_session()

    create_agent_memory(
        session,
        agent_id="daily-brief-agent",
        memory_type="summary",
        content="Summarized AI infrastructure notes.",
        importance="medium",
    )

    memories = list_agent_memory(session)
    assert len(memories) == 1
    assert memories[0].agent_id == "daily-brief-agent"
    assert memories[0].memory_type.value == "summary"
    assert memories[0].importance.value == "medium"


def test_create_and_list_decision_log():
    session = make_session()

    create_decision_log(
        session,
        title="Keep dry-run",
        decision="Keep all agents dry-run.",
        rationale="Approval workflow is future scope.",
        proposed_by="codex",
        reviewed_by="human",
        approved_by="human",
        status="approved",
        related_request_id="request-123",
    )

    decisions = list_decision_logs(session)
    assert len(decisions) == 1
    assert decisions[0].status.value == "approved"
    assert decisions[0].related_request_id == "request-123"
