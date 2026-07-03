import pytest


fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.app.main import app


def test_agents_endpoint_lists_echo_agent():
    client = TestClient(app)

    response = client.get("/agents")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "echo-agent"


def test_agents_run_endpoint_runs_echo_agent():
    client = TestClient(app)

    response = client.post(
        "/agents/run",
        json={
            "agent_id": "echo-agent",
            "input": {
                "message": "hello",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "agent_id": "echo-agent",
        "status": "success",
        "output": {
            "message": "hello",
            "echo": True,
        },
    }


def test_agents_run_endpoint_returns_clear_error_for_invalid_agent():
    client = TestClient(app)

    response = client.post(
        "/agents/run",
        json={
            "agent_id": "missing-agent",
            "input": {
                "message": "hello",
            },
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown agent_id: missing-agent"

