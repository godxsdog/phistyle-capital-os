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


def create_triage_result(client, request_id, recommendation="escalate_to_brain"):
    response = client.post(
        "/decisions/triage/override",
        json={
            "decision_request_id": request_id,
            "risk_level": "high",
            "recommendation": recommendation,
            "rationale": "Manual triage.",
            "flags": "manual",
            "created_by": "human-triage",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_brain_run_without_triage_uses_rule_zero():
    client = make_client()
    request = create_decision_request(client, risk_level="low", decision_type="travel")

    response = client.post("/decisions/brain/run", json={"decision_request_id": request["id"]})

    assert response.status_code == 200
    assert response.json()["recommendation"] == "human_review_required"
    assert response.json()["confidence"] == "high"
    assert response.json()["triage_result_id"] is None


def test_brain_run_with_nonexistent_triage_uses_rule_zero_not_error():
    client = make_client()
    request = create_decision_request(client, risk_level="low", decision_type="travel")

    response = client.post(
        "/decisions/brain/run",
        json={"decision_request_id": request["id"], "triage_result_id": 999},
    )

    assert response.status_code == 200
    assert response.json()["recommendation"] == "human_review_required"
    assert response.json()["triage_result_id"] is None


def test_brain_run_reject_request_wins_over_empty_context():
    client = make_client()
    request = create_decision_request(client, context="", risk_level="low", decision_type="travel")
    triage_result = create_triage_result(client, request["id"], recommendation="reject_request")

    response = client.post(
        "/decisions/brain/run",
        json={"decision_request_id": request["id"], "triage_result_id": triage_result["id"]},
    )

    assert response.status_code == 200
    assert response.json()["recommendation"] == "reject"


def test_brain_run_escalate_to_brain_requires_human_review():
    client = make_client()
    request = create_decision_request(client)
    triage_result = create_triage_result(client, request["id"], recommendation="escalate_to_brain")

    response = client.post(
        "/decisions/brain/run",
        json={"decision_request_id": request["id"], "triage_result_id": triage_result["id"]},
    )

    assert response.status_code == 200
    assert response.json()["recommendation"] == "human_review_required"
    assert response.json()["required_human_approval"] is True


def test_brain_run_missing_context_requests_more_context():
    client = make_client()
    request = create_decision_request(client, context="", risk_level="low", decision_type="travel")
    triage_result = create_triage_result(client, request["id"], recommendation="handle_locally")

    response = client.post(
        "/decisions/brain/run",
        json={"decision_request_id": request["id"], "triage_result_id": triage_result["id"]},
    )

    assert response.status_code == 200
    assert response.json()["recommendation"] == "request_more_context"


def test_brain_review_lists_for_request_and_deterministic_rules_do_not_set_decision_log_id():
    client = make_client()
    request = create_decision_request(client, risk_level="low", decision_type="travel")
    triage_result = create_triage_result(client, request["id"], recommendation="handle_locally")

    created = client.post(
        "/decisions/brain/run",
        json={"decision_request_id": request["id"], "triage_result_id": triage_result["id"]},
    ).json()

    assert created["recommendation"] == "proceed"
    assert created["proposed_decision_log_id"] is None
    assert client.get("/decisions/brain-reviews").json()[0]["id"] == created["id"]
    assert client.get(f"/decisions/requests/{request['id']}/brain-reviews").json()[0]["id"] == created["id"]


def test_brain_override_rejects_reserved_created_by():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/brain/override",
        json={
            "decision_request_id": request["id"],
            "recommendation": "human_review_required",
            "rationale": "Manual review.",
            "confidence": "medium",
            "required_human_approval": True,
            "created_by": "brain-orchestrator",
        },
    )

    assert response.status_code == 422


def test_brain_override_invalid_decision_request_id_rejected():
    client = make_client()

    response = client.post(
        "/decisions/brain/override",
        json={
            "decision_request_id": 999,
            "recommendation": "human_review_required",
            "rationale": "Manual review.",
            "confidence": "medium",
            "required_human_approval": True,
            "created_by": "human",
        },
    )

    assert response.status_code == 404


def test_brain_override_invalid_triage_result_id_rejected():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/brain/override",
        json={
            "decision_request_id": request["id"],
            "triage_result_id": 999,
            "recommendation": "human_review_required",
            "rationale": "Manual review.",
            "confidence": "medium",
            "required_human_approval": True,
            "created_by": "human",
        },
    )

    assert response.status_code == 404


def test_brain_override_invalid_recommendation_rejected():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/brain/override",
        json={
            "decision_request_id": request["id"],
            "recommendation": "approve_and_execute",
            "rationale": "Manual review.",
            "confidence": "medium",
            "required_human_approval": True,
            "created_by": "human",
        },
    )

    assert response.status_code == 422


def test_brain_override_invalid_confidence_rejected():
    client = make_client()
    request = create_decision_request(client)

    response = client.post(
        "/decisions/brain/override",
        json={
            "decision_request_id": request["id"],
            "recommendation": "human_review_required",
            "rationale": "Manual review.",
            "confidence": "certain",
            "required_human_approval": True,
            "created_by": "human",
        },
    )

    assert response.status_code == 422


def test_brain_review_does_not_change_decision_request_status_or_trigger_actions(monkeypatch):
    client = make_client()
    request = create_decision_request(client, status="submitted", risk_level="low", decision_type="travel")
    triage_result = create_triage_result(client, request["id"], recommendation="handle_locally")

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("Brain scaffold must not call LLM providers")

    def fail_if_agent_workflow_runs(*args, **kwargs):
        raise AssertionError("BrainReview must not trigger unrelated workflows")

    monkeypatch.setattr("backend.app.main.DeepSeekProvider.chat", fail_if_llm_runs)
    monkeypatch.setattr("backend.app.main.run_agent", fail_if_agent_workflow_runs)

    response = client.post(
        "/decisions/brain/run",
        json={"decision_request_id": request["id"], "triage_result_id": triage_result["id"]},
    )

    assert response.status_code == 200
    assert response.json()["recommendation"] == "proceed"
    unchanged = client.get(f"/decisions/requests/{request['id']}")
    assert unchanged.json()["status"] == "submitted"

