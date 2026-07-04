import pytest


pytest.importorskip("sqlalchemy")
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import decision_request, knowledge  # noqa: F401


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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


def request_payload(**overrides):
    payload = {
        "app_id": "capital",
        "decision_type": "investment",
        "question": "Should I reduce AVGO exposure?",
        "context": "AVGO is now concentrated in the portfolio.",
        "options": "hold | reduce 20% | hedge",
        "risk_level": "high",
        "status": "submitted",
        "created_by": "Kaichang",
        "related_knowledge_document_id": None,
        "related_decision_log_id": None,
    }
    payload.update(overrides)
    return payload


def test_create_and_list_decision_request():
    client = make_client()

    response = client.post("/decisions/requests", json=request_payload())

    assert response.status_code == 200
    assert response.json()["app_id"] == "capital"
    listed = client.get("/decisions/requests")
    assert listed.status_code == 200
    assert listed.json()[0]["question"] == "Should I reduce AVGO exposure?"


def test_get_decision_request_by_id():
    client = make_client()
    created = client.post("/decisions/requests", json=request_payload()).json()

    response = client.get(f"/decisions/requests/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_update_status_allows_skip_ahead_transition():
    client = make_client()
    created = client.post("/decisions/requests", json=request_payload(status="draft")).json()

    response = client.patch(
        f"/decisions/requests/{created['id']}/status",
        json={"status": "human_approved"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "human_approved"


def test_patch_human_approved_to_draft_returns_409_and_preserves_state():
    client = make_client()
    created = client.post("/decisions/requests", json=request_payload(status="human_approved")).json()

    response = client.patch(
        f"/decisions/requests/{created['id']}/status",
        json={"status": "draft"},
    )
    unchanged = client.get(f"/decisions/requests/{created['id']}")

    assert response.status_code == 409
    assert "human_approved" in response.json()["detail"]
    assert "draft" in response.json()["detail"]
    assert unchanged.status_code == 200
    assert unchanged.json()["status"] == "human_approved"


def test_patch_human_approved_to_archived_returns_200():
    client = make_client()
    created = client.post("/decisions/requests", json=request_payload(status="human_approved")).json()

    response = client.patch(
        f"/decisions/requests/{created['id']}/status",
        json={"status": "archived"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_invalid_decision_type_rejected():
    client = make_client()

    response = client.post("/decisions/requests", json=request_payload(decision_type="portfolio"))

    assert response.status_code == 422


def test_invalid_risk_level_rejected():
    client = make_client()

    response = client.post("/decisions/requests", json=request_payload(risk_level="urgent"))

    assert response.status_code == 422


def test_invalid_status_rejected():
    client = make_client()

    response = client.post("/decisions/requests", json=request_payload(status="approved"))

    assert response.status_code == 422


def test_invalid_app_id_rejected():
    client = make_client()

    response = client.post("/decisions/requests", json=request_payload(app_id="platform"))

    assert response.status_code == 422
    assert "Unknown app_id" in response.json()["detail"]


def test_nonexistent_related_knowledge_document_rejected_by_fk():
    client = make_client()

    response = client.post(
        "/decisions/requests",
        json=request_payload(related_knowledge_document_id=999),
    )

    assert response.status_code == 400


def test_nonexistent_related_decision_log_rejected_by_fk():
    client = make_client()

    response = client.post(
        "/decisions/requests",
        json=request_payload(related_decision_log_id=999),
    )

    assert response.status_code == 400


def test_human_approved_status_does_not_trigger_actions(monkeypatch):
    client = make_client()
    created = client.post("/decisions/requests", json=request_payload(status="draft")).json()

    def fail_if_agent_runs(*args, **kwargs):
        raise AssertionError("Decision Request status updates must not run agents")

    monkeypatch.setattr("backend.app.main.run_agent", fail_if_agent_runs)

    response = client.patch(
        f"/decisions/requests/{created['id']}/status",
        json={"status": "human_approved"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "human_approved"


def test_decision_request_endpoints_do_not_call_llm_or_network(monkeypatch):
    client = make_client()

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("Decision Request endpoints must not call LLM providers")

    monkeypatch.setattr("backend.app.main.DeepSeekProvider.chat", fail_if_llm_runs)

    response = client.post("/decisions/requests", json=request_payload())

    assert response.status_code == 200
