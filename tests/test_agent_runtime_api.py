import pytest


fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.app.main import app
from services.llm_router.types import LLMResponse


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


def test_agents_run_endpoint_runs_daily_brief_agent(monkeypatch):
    client = TestClient(app)

    def mock_chat(self, request):
        assert request.role.value == "summarizer"
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content=(
                '{"summary":"AI infrastructure brief summary.",'
                '"key_points":["Demand remains elevated"],'
                '"risk_flags":["Supply chain constraints"]}'
            ),
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    response = client.post(
        "/agents/run",
        json={
            "agent_id": "daily-brief-agent",
            "input": {
                "topic": "AI infrastructure",
                "text": "Long text to summarize.",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "agent_id": "daily-brief-agent",
        "status": "success",
        "output": {
            "topic": "AI infrastructure",
            "summary": "AI infrastructure brief summary.",
            "key_points": ["Demand remains elevated"],
            "risk_flags": ["Supply chain constraints"],
            "source": "manual_input",
        },
    }
