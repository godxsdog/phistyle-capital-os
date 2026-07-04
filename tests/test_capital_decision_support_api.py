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


def capital_payload(**overrides):
    payload = {
        "question": "  Should I reduce AVGO exposure?  ",
        "context": "  AVGO is now concentrated in the portfolio.  ",
        "options": "  hold | reduce 20% | hedge  ",
        "risk_level": "high",
        "created_by": "  Kaichang  ",
    }
    payload.update(overrides)
    return payload


def create_capital_decision(client):
    response = client.post("/capital/decisions", json=capital_payload())
    assert response.status_code == 200
    return response.json()


def test_create_capital_decision_endpoint_owns_fields_and_trims():
    client = make_client()

    response = client.post("/capital/decisions", json=capital_payload())

    assert response.status_code == 200
    assert response.json()["app_id"] == "capital"
    assert response.json()["decision_type"] == "investment"
    assert response.json()["status"] == "submitted"
    request = client.get(f"/decisions/requests/{response.json()['decision_request_id']}").json()
    assert request["question"] == "Should I reduce AVGO exposure?"
    assert request["context"] == "AVGO is now concentrated in the portfolio."
    assert request["options"] == "hold | reduce 20% | hedge"
    assert request["created_by"] == "Kaichang"


@pytest.mark.parametrize("field", ["app_id", "decision_type", "status"])
def test_create_capital_decision_endpoint_forbids_owned_field_overrides(field):
    client = make_client()
    payload = capital_payload(**{field: "not-allowed"})

    response = client.post("/capital/decisions", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["question", "context", "options", "created_by"])
def test_create_capital_decision_endpoint_rejects_empty_required_text(field):
    client = make_client()

    response = client.post("/capital/decisions", json=capital_payload(**{field: "   "}))

    assert response.status_code == 422


def test_create_capital_decision_endpoint_rejects_invalid_risk_level():
    client = make_client()

    response = client.post("/capital/decisions", json=capital_payload(risk_level="urgent"))

    assert response.status_code == 422


def test_capital_pipeline_endpoint_runs_and_is_idempotent(monkeypatch):
    client = make_client()
    created = create_capital_decision(client)

    def fail_if_llm_runs(*args, **kwargs):
        raise AssertionError("Capital pipeline must not call LLM providers")

    def fail_if_agent_workflow_runs(*args, **kwargs):
        raise AssertionError("Capital pipeline endpoint must not use generic agent workflow execution")

    monkeypatch.setattr("backend.app.main.DeepSeekProvider.chat", fail_if_llm_runs)
    monkeypatch.setattr("backend.app.main.run_agent", fail_if_agent_workflow_runs)

    first = client.post(f"/capital/decisions/{created['decision_request_id']}/run")
    second = client.post(f"/capital/decisions/{created['decision_request_id']}/run")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["decision_request_status"] == "brain_reviewed"
    assert first.json()["decision_log_status"] == "proposed"
    assert first.json()["decision_log_approved_by"] is None
    assert first.json()["requires_human_review"] is True
    assert second.json()["triage_result_id"] == first.json()["triage_result_id"]
    assert second.json()["brain_review_id"] == first.json()["brain_review_id"]
    assert second.json()["decision_log_id"] == first.json()["decision_log_id"]
    assert len(client.get("/decisions/triage").json()) == 1
    assert len(client.get("/decisions/brain-reviews").json()) == 1
    assert len(client.get("/knowledge/decisions").json()) == 1
    assert client.get("/decisions/human-reviews").json() == []


def test_capital_pipeline_rejects_non_capital_request():
    client = make_client()
    response = client.post(
        "/decisions/requests",
        json={
            "app_id": "travel",
            "decision_type": "travel",
            "question": "Book a hotel?",
            "context": "Planning a trip.",
            "risk_level": "medium",
            "status": "submitted",
        },
    )
    assert response.status_code == 200

    run_response = client.post(f"/capital/decisions/{response.json()['id']}/run")

    assert run_response.status_code == 400


def test_capital_summary_before_and_after_human_review():
    client = make_client()
    created = create_capital_decision(client)
    run_response = client.post(f"/capital/decisions/{created['decision_request_id']}/run").json()

    before = client.get(f"/capital/decisions/{created['decision_request_id']}")

    assert before.status_code == 200
    assert before.json()["decision_request"]["status"] == "brain_reviewed"
    assert before.json()["triage_result"]["id"] == run_response["triage_result_id"]
    assert before.json()["brain_review"]["id"] == run_response["brain_review_id"]
    assert before.json()["decision_log"]["id"] == run_response["decision_log_id"]
    assert before.json()["decision_log"]["status"] == "proposed"
    assert before.json()["human_review"] is None
    assert before.json()["requires_human_review"] is True

    review = client.post(
        f"/decisions/decision-logs/{run_response['decision_log_id']}/human-review",
        json={"reviewer": "Kaichang", "review_decision": "approve"},
    )
    after_run = client.post(f"/capital/decisions/{created['decision_request_id']}/run")
    after = client.get(f"/capital/decisions/{created['decision_request_id']}")

    assert review.status_code == 200
    assert after_run.json()["decision_request_status"] == "human_approved"
    assert after_run.json()["decision_log_status"] == "approved"
    assert after_run.json()["decision_log_approved_by"] == "Kaichang"
    assert after_run.json()["requires_human_review"] is False
    assert after.json()["human_review"]["reviewer"] == "Kaichang"
    assert after.json()["human_review"]["review_decision"] == "approve"
    assert after.json()["requires_human_review"] is False


def test_capital_pipeline_after_reject_preserves_final_state():
    client = make_client()
    created = create_capital_decision(client)
    run_response = client.post(f"/capital/decisions/{created['decision_request_id']}/run").json()
    review = client.post(
        f"/decisions/decision-logs/{run_response['decision_log_id']}/human-review",
        json={"reviewer": "Kaichang", "review_decision": "reject"},
    )
    rerun = client.post(f"/capital/decisions/{created['decision_request_id']}/run")

    assert review.status_code == 200
    assert rerun.json()["decision_request_status"] == "rejected"
    assert rerun.json()["decision_log_status"] == "rejected"
    assert rerun.json()["decision_log_approved_by"] is None
    assert rerun.json()["requires_human_review"] is False


def test_capital_list_endpoint_returns_only_capital_investment_requests():
    client = make_client()
    capital = create_capital_decision(client)
    travel = client.post(
        "/decisions/requests",
        json={
            "app_id": "travel",
            "decision_type": "travel",
            "question": "Book a hotel?",
            "context": "Planning a trip.",
            "risk_level": "medium",
            "status": "submitted",
        },
    )
    assert travel.status_code == 200

    response = client.get("/capital/decisions")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [capital["decision_request_id"]]
    assert response.json()[0]["app_id"] == "capital"
    assert response.json()[0]["decision_type"] == "investment"
