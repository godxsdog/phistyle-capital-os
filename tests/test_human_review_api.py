import pytest


pytest.importorskip("sqlalchemy")
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import brain_review, decision_request, human_review, knowledge, triage  # noqa: F401


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


def create_request(client):
    response = client.post(
        "/decisions/requests",
        json={
            "app_id": "capital",
            "decision_type": "investment",
            "question": "Should I reduce AVGO exposure?",
            "context": "AVGO is concentrated.",
            "risk_level": "high",
            "status": "submitted",
            "created_by": "Kaichang",
        },
    )
    assert response.status_code == 200
    return response.json()


def create_proposed_decision_log(client, request):
    response = client.post(
        "/knowledge/decisions",
        json={
            "title": request["question"],
            "decision": "human_review_required",
            "rationale": "High risk concentration.",
            "proposed_by": "brain-orchestrator",
            "reviewed_by": "brain-orchestrator",
            "status": "proposed",
            "related_request_id": str(request["id"]),
        },
    )
    assert response.status_code == 200
    return response.json()


def test_human_review_endpoint_approves_decision_record_only(monkeypatch):
    client = make_client()
    request = create_request(client)
    decision_log = create_proposed_decision_log(client, request)

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("Human review endpoint must not call LLM providers")

    def fail_if_agent_runs(*args, **kwargs):
        raise AssertionError("Human review endpoint must not run agents or workflows")

    monkeypatch.setattr("backend.app.main.DeepSeekProvider.chat", fail_if_llm_runs)
    monkeypatch.setattr("backend.app.main.run_agent", fail_if_agent_runs)

    response = client.post(
        f"/decisions/decision-logs/{decision_log['id']}/human-review",
        json={
            "reviewer": "  Kaichang  ",
            "review_decision": "approve",
            "comment": "Reviewed and approved as a decision record.",
        },
    )

    assert response.status_code == 200
    assert response.json()["decision_log_status"] == "approved"
    assert response.json()["decision_request_status"] == "human_approved"
    assert response.json()["review_decision"] == "approve"
    approved_decision = client.get("/knowledge/decisions").json()[0]
    approved_request = client.get(f"/decisions/requests/{request['id']}").json()
    human_review_record = client.get("/decisions/human-reviews").json()[0]
    assert approved_decision["status"] == "approved"
    assert approved_decision["approved_by"] == "Kaichang"
    assert approved_request["status"] == "human_approved"
    assert approved_request["related_decision_log_id"] == decision_log["id"]
    assert human_review_record["reviewer"] == "Kaichang"
    assert human_review_record["decision_log_id"] == decision_log["id"]


def test_human_review_endpoint_rejects_decision_record_only():
    client = make_client()
    request = create_request(client)
    decision_log = create_proposed_decision_log(client, request)

    response = client.post(
        f"/decisions/decision-logs/{decision_log['id']}/human-review",
        json={
            "reviewer": "Kaichang",
            "review_decision": "reject",
            "comment": "Insufficient context.",
        },
    )

    assert response.status_code == 200
    assert response.json()["decision_log_status"] == "rejected"
    assert response.json()["decision_request_status"] == "rejected"
    rejected_decision = client.get("/knowledge/decisions").json()[0]
    rejected_request = client.get(f"/decisions/requests/{request['id']}").json()
    assert rejected_decision["status"] == "rejected"
    assert rejected_decision["approved_by"] is None
    assert rejected_request["status"] == "rejected"
    assert rejected_request["related_decision_log_id"] == decision_log["id"]


def test_human_review_read_endpoints_are_read_only():
    client = make_client()
    request = create_request(client)
    decision_log = create_proposed_decision_log(client, request)
    review = client.post(
        f"/decisions/decision-logs/{decision_log['id']}/human-review",
        json={"reviewer": "Kaichang", "review_decision": "approve"},
    ).json()

    all_reviews = client.get("/decisions/human-reviews")
    decision_reviews = client.get(f"/decisions/decision-logs/{decision_log['id']}/human-reviews")

    assert all_reviews.status_code == 200
    assert decision_reviews.status_code == 200
    assert all_reviews.json()[0]["id"] == review["human_review_id"]
    assert decision_reviews.json()[0]["id"] == review["human_review_id"]


def test_human_review_endpoint_rejects_second_review():
    client = make_client()
    request = create_request(client)
    decision_log = create_proposed_decision_log(client, request)
    first = client.post(
        f"/decisions/decision-logs/{decision_log['id']}/human-review",
        json={"reviewer": "Kaichang", "review_decision": "approve"},
    )

    second = client.post(
        f"/decisions/decision-logs/{decision_log['id']}/human-review",
        json={"reviewer": "Someone", "review_decision": "reject"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(client.get("/decisions/human-reviews").json()) == 1


def test_human_review_endpoint_validation_errors_are_clear():
    client = make_client()
    request = create_request(client)
    decision_log = create_proposed_decision_log(client, request)

    missing_reviewer = client.post(
        f"/decisions/decision-logs/{decision_log['id']}/human-review",
        json={"reviewer": "   ", "review_decision": "approve"},
    )
    bad_decision = client.post(
        f"/decisions/decision-logs/{decision_log['id']}/human-review",
        json={"reviewer": "Kaichang", "review_decision": "approved"},
    )
    missing_log = client.post(
        "/decisions/decision-logs/999/human-review",
        json={"reviewer": "Kaichang", "review_decision": "approve"},
    )

    assert missing_reviewer.status_code == 400
    assert bad_decision.status_code == 400
    assert missing_log.status_code == 404
    assert client.get("/decisions/human-reviews").json() == []
