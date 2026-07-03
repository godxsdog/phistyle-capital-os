import json

import pytest

from services.llm_router.providers.fable import FableProvider
from services.llm_router.router import provider_id_for_role, route_task
from services.llm_router.types import LLMRequest, ModelRole, TaskClass


def test_orchestrator_role_routes_to_fable_provider():
    assert provider_id_for_role(ModelRole.ORCHESTRATOR) == "fable"


def test_fable_task_classes_route_to_fable_orchestrator():
    for task_class in (
        TaskClass.HIGH_RISK_ARCHITECTURE,
        TaskClass.FINAL_DECISION,
        TaskClass.INVESTMENT_THESIS,
        TaskClass.MULTI_AGENT_ARBITRATION,
    ):
        decision = route_task(task_class)

        assert decision.provider_id == "fable"
        assert decision.role == ModelRole.ORCHESTRATOR


def test_low_risk_summary_does_not_route_to_fable():
    decision = route_task(TaskClass.DOCS_FORMATTING_SUMMARIES)

    assert decision.provider_id != "fable"


def test_fable_provider_dry_run_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("FABLE_API_KEY", raising=False)
    monkeypatch.setenv("FABLE_BASE_URL", "https://example.fable.local")

    provider = FableProvider()
    response = provider.chat(LLMRequest(role=ModelRole.ORCHESTRATOR, prompt="decide this"))

    assert response.provider_id == "fable"
    assert response.dry_run is True
    assert response.content == "[dry-run:fable] decide this"
    assert response.metadata["base_url"] == "https://example.fable.local"
    assert "api_key" not in response.metadata


def test_fable_provider_rejects_non_orchestrator_roles():
    provider = FableProvider(api_key="")

    with pytest.raises(ValueError, match="restricted to orchestrator"):
        provider.chat(LLMRequest(role=ModelRole.SUMMARIZER, prompt="summarize this"))


def test_fable_provider_uses_mocked_chat_completion(monkeypatch):
    captured = {}

    class MockHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "mock decision",
                            },
                            "finish_reason": "stop",
                        }
                    ]
                }
            ).encode("utf-8")

    def mock_urlopen(request, timeout):
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return MockHTTPResponse()

    monkeypatch.setenv("FABLE_API_KEY", "test-fable-key-not-real")
    monkeypatch.setenv("FABLE_BASE_URL", "https://example.fable.local")
    monkeypatch.setattr("services.llm_router.providers.fable.urllib_request.urlopen", mock_urlopen)

    provider = FableProvider(timeout_seconds=11)
    response = provider.chat(LLMRequest(role=ModelRole.ORCHESTRATOR, prompt="decide this"))

    assert response.dry_run is False
    assert response.content == "mock decision"
    assert response.metadata["role"] == "orchestrator"
    assert response.metadata["finish_reason"] == "stop"
    assert response.metadata["thinking_policy"] == "separate_or_discard"
    assert response.metadata["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }
    assert captured["authorization"] == "Bearer test-fable-key-not-real"
    assert captured["body"]["messages"][-1] == {
        "role": "user",
        "content": "decide this",
    }
    assert captured["timeout"] == 11
