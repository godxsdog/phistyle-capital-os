import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import knowledge  # noqa: F401


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def test_create_and_list_knowledge_document():
    client = make_client()

    response = client.post(
        "/knowledge/documents",
        json={
            "title": "AI infrastructure note",
            "content": "Short summary only.",
            "source_type": "manual",
            "tags": "ai,infra",
            "storage_backend": "local",
        },
    )

    assert response.status_code == 200
    assert response.json()["source_type"] == "manual"
    assert client.get("/knowledge/documents").json()[0]["title"] == "AI infrastructure note"


def test_create_and_list_knowledge_document_with_nas_file_path_without_reading_file():
    client = make_client()

    response = client.post(
        "/knowledge/documents",
        json={
            "title": "NAS reference",
            "content": "Short summary only.",
            "source_type": "import",
            "tags": "nas",
            "storage_backend": "nas",
            "file_path": "/Volumes/PhiStyleOS/capital/reports/not-present.pdf",
        },
    )

    assert response.status_code == 200
    assert response.json()["storage_backend"] == "nas"
    assert response.json()["file_path"] == "/Volumes/PhiStyleOS/capital/reports/not-present.pdf"


def test_invalid_storage_backend_rejected():
    client = make_client()

    response = client.post(
        "/knowledge/documents",
        json={
            "title": "Bad backend",
            "content": "Short summary only.",
            "source_type": "manual",
            "storage_backend": "smb",
        },
    )

    assert response.status_code == 422


def test_invalid_source_type_rejected():
    client = make_client()

    response = client.post(
        "/knowledge/documents",
        json={
            "title": "Bad source",
            "content": "Short summary only.",
            "source_type": "crawler",
            "storage_backend": "local",
        },
    )

    assert response.status_code == 422


def test_create_and_list_agent_memory():
    client = make_client()

    response = client.post(
        "/knowledge/memories",
        json={
            "agent_id": "daily-brief-agent",
            "memory_type": "summary",
            "content": "Summary memory.",
            "importance": "medium",
        },
    )

    assert response.status_code == 200
    assert response.json()["memory_type"] == "summary"
    assert client.get("/knowledge/memories").json()[0]["agent_id"] == "daily-brief-agent"


def test_invalid_memory_type_rejected():
    client = make_client()

    response = client.post(
        "/knowledge/memories",
        json={
            "agent_id": "daily-brief-agent",
            "memory_type": "profile",
            "content": "Summary memory.",
            "importance": "medium",
        },
    )

    assert response.status_code == 422


def test_invalid_importance_rejected():
    client = make_client()

    response = client.post(
        "/knowledge/memories",
        json={
            "agent_id": "daily-brief-agent",
            "memory_type": "summary",
            "content": "Summary memory.",
            "importance": "urgent",
        },
    )

    assert response.status_code == 422


def test_create_and_list_decision_log():
    client = make_client()

    response = client.post(
        "/knowledge/decisions",
        json={
            "title": "Keep dry-run",
            "decision": "Keep all agents dry-run.",
            "rationale": "Approval workflow is future scope.",
            "proposed_by": "codex",
            "reviewed_by": "human",
            "approved_by": "human",
            "status": "approved",
            "related_request_id": "request-123",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert client.get("/knowledge/decisions").json()[0]["related_request_id"] == "request-123"


def test_invalid_decision_status_rejected():
    client = make_client()

    response = client.post(
        "/knowledge/decisions",
        json={
            "title": "Bad status",
            "decision": "Unknown.",
            "rationale": "Invalid.",
            "status": "merged",
        },
    )

    assert response.status_code == 422


def test_decision_post_persists_record_only_without_approval_side_effects(monkeypatch):
    client = make_client()

    def fail_if_agent_runs(*args, **kwargs):
        raise AssertionError("Decision log endpoint must not run agents or workflows")

    monkeypatch.setattr("backend.app.main.run_agent", fail_if_agent_runs)

    response = client.post(
        "/knowledge/decisions",
        json={
            "title": "Advisory approval record",
            "decision": "Approved elsewhere.",
            "rationale": "Only recording the decision.",
            "status": "approved",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_knowledge_endpoints_do_not_call_llm_or_network(monkeypatch):
    client = make_client()

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("Knowledge endpoints must not call LLM providers")

    monkeypatch.setattr("backend.app.main.DeepSeekProvider.chat", fail_if_llm_runs)

    response = client.post(
        "/knowledge/documents",
        json={
            "title": "No LLM",
            "content": "Stored as provided.",
            "source_type": "manual",
            "storage_backend": "local",
        },
    )

    assert response.status_code == 200
