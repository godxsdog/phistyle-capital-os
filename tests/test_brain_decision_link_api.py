import pytest


pytest.importorskip("sqlalchemy")
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import brain_review, decision_request, knowledge, triage  # noqa: F401


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


def create_decision_request(client, **overrides):
    payload = {
        "app_id": "capital",
        "decision_type": "investment",
        "question": "Should I reduce AVGO exposure?",
        "context": "AVGO is concentrated.",
        "options": "hold | reduce",
        "risk_level": "high",
        "status": "submitted",
        "created_by": "Kaichang",
    }
    payload.update(overrides)
    response = client.post("/decisions/requests", json=payload)
    assert response.status_code == 200
    return response.json()


def create_brain_review(client, request_id):
    response = client.post("/decisions/brain/run", json={"decision_request_id": request_id})
    assert response.status_code == 200
    return response.json()


def test_endpoint_creates_draft_and_updates_link():
    client = make_client()
    request = create_decision_request(client)
    review = create_brain_review(client, request["id"])

    response = client.post(
        f"/decisions/brain-reviews/{review['id']}/decision-log-draft",
        json={"proposed_by": "Kaichang"},
    )

    assert response.status_code == 200
    assert response.json()["brain_review_id"] == review["id"]
    assert response.json()["decision_log_status"] == "proposed"
    assert response.json()["created"] is True
    updated_review = client.get(f"/decisions/requests/{request['id']}/brain-reviews").json()[0]
    assert updated_review["proposed_decision_log_id"] == response.json()["decision_log_id"]
    decision_log = client.get("/knowledge/decisions").json()[0]
    assert decision_log["status"] == "proposed"
    assert decision_log["approved_by"] is None
    assert decision_log["title"] == request["question"]
    assert decision_log["decision"] == review["recommendation"]
    assert decision_log["rationale"] == review["rationale"]
    assert decision_log["proposed_by"] == "Kaichang"


def test_endpoint_second_call_is_idempotent_without_duplicate():
    client = make_client()
    request = create_decision_request(client)
    review = create_brain_review(client, request["id"])

    first = client.post(f"/decisions/brain-reviews/{review['id']}/decision-log-draft", json={})
    second = client.post(f"/decisions/brain-reviews/{review['id']}/decision-log-draft", json={})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["decision_log_id"] == second.json()["decision_log_id"]
    assert len(client.get("/knowledge/decisions").json()) == 1


def test_brain_run_still_does_not_create_decision_log_automatically():
    client = make_client()
    request = create_decision_request(client)

    review = create_brain_review(client, request["id"])

    assert review["proposed_decision_log_id"] is None
    assert client.get("/knowledge/decisions").json() == []


def test_creating_draft_does_not_change_decision_request_status_or_trigger_actions(monkeypatch):
    client = make_client()
    request = create_decision_request(client, status="submitted")
    review = create_brain_review(client, request["id"])

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("DecisionLog draft creation must not call LLM providers")

    def fail_if_agent_workflow_runs(*args, **kwargs):
        raise AssertionError("DecisionLog draft creation must not trigger workflows")

    monkeypatch.setattr("backend.app.main.DeepSeekProvider.chat", fail_if_llm_runs)
    monkeypatch.setattr("backend.app.main.run_agent", fail_if_agent_workflow_runs)

    response = client.post(f"/decisions/brain-reviews/{review['id']}/decision-log-draft", json={})

    assert response.status_code == 200
    unchanged = client.get(f"/decisions/requests/{request['id']}")
    assert unchanged.json()["status"] == "submitted"


def test_invalid_brain_review_id_rejected():
    client = make_client()

    response = client.post("/decisions/brain-reviews/999/decision-log-draft", json={})

    assert response.status_code == 404


def test_api_does_not_accept_approved_by_input():
    client = make_client()
    request = create_decision_request(client)
    review = create_brain_review(client, request["id"])

    response = client.post(
        f"/decisions/brain-reviews/{review['id']}/decision-log-draft",
        json={"approved_by": "Kaichang"},
    )

    assert response.status_code == 422

