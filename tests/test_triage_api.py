import pytest


pytest.importorskip("sqlalchemy")
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import decision_request, knowledge, triage  # noqa: F401


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
        "context": "AVGO is concentrated.",
        "options": "hold | reduce",
        "risk_level": "high",
        "status": "submitted",
        "created_by": "Kaichang",
    }
    payload.update(overrides)
    return payload


def create_decision_request(client, **overrides):
    response = client.post("/decisions/requests", json=request_payload(**overrides))
    assert response.status_code == 200
    return response.json()


def test_triage_run_invokes_rule_engine_and_persists_system_creator():
    client = make_client()
    request = create_decision_request(client, decision_type="travel", risk_level="medium")

    response = client.post("/decisions/triage/run", json={"decision_request_id": request["id"]})

    assert response.status_code == 200
    assert response.json()["created_by"] == "triage-agent"
    assert response.json()["recommendation"] == "use_worker_model"
    assert client.get("/decisions/triage").json()[0]["id"] == response.json()["id"]


def test_triage_override_rejects_reserved_created_by():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/triage/override",
        json={
            "decision_request_id": request["id"],
            "risk_level": "high",
            "recommendation": "escalate_to_brain",
            "rationale": "Manual correction.",
            "flags": "investment,high-risk",
            "created_by": "triage-agent",
        },
    )

    assert response.status_code == 422


def test_triage_override_creates_and_lists_for_decision_request():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/triage/override",
        json={
            "decision_request_id": request["id"],
            "risk_level": "high",
            "recommendation": "escalate_to_brain",
            "rationale": "Manual correction.",
            "flags": "investment,high-risk",
            "created_by": "human-reviewer",
        },
    )

    assert response.status_code == 200
    assert response.json()["flags"] == "investment,high-risk"
    listed = client.get(f"/decisions/requests/{request['id']}/triage")
    assert listed.status_code == 200
    assert listed.json()[0]["created_by"] == "human-reviewer"


def test_triage_invalid_decision_request_id_rejected():
    client = make_client()

    response = client.post("/decisions/triage/run", json={"decision_request_id": 999})

    assert response.status_code == 404


def test_triage_override_invalid_risk_level_rejected():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/triage/override",
        json={
            "decision_request_id": request["id"],
            "risk_level": "urgent",
            "recommendation": "escalate_to_brain",
            "rationale": "Manual correction.",
            "created_by": "human",
        },
    )

    assert response.status_code == 422


def test_triage_override_invalid_recommendation_rejected():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/triage/override",
        json={
            "decision_request_id": request["id"],
            "risk_level": "high",
            "recommendation": "call_fable_now",
            "rationale": "Manual correction.",
            "created_by": "human",
        },
    )

    assert response.status_code == 422


def test_triage_reject_request_does_not_modify_decision_request_status():
    client = make_client()
    request = create_decision_request(client, question="", risk_level="high", status="submitted")

    response = client.post("/decisions/triage/run", json={"decision_request_id": request["id"]})

    assert response.status_code == 200
    assert response.json()["recommendation"] == "reject_request"
    unchanged = client.get(f"/decisions/requests/{request['id']}")
    assert unchanged.json()["status"] == "submitted"


def test_triage_does_not_call_llm_or_fable_or_execute_actions(monkeypatch):
    client = make_client()
    request = create_decision_request(client)

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("Triage must not call LLM providers")

    def fail_if_agent_workflow_runs(*args, **kwargs):
        raise AssertionError("Triage must not trigger unrelated workflows")

    monkeypatch.setattr("backend.app.main.DeepSeekProvider.chat", fail_if_llm_runs)
    monkeypatch.setattr("backend.app.main.run_agent", fail_if_agent_workflow_runs)

    response = client.post("/decisions/triage/run", json={"decision_request_id": request["id"]})

    assert response.status_code == 200
    assert response.json()["recommendation"] == "escalate_to_brain"

