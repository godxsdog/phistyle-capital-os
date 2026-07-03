import json

from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.router import provider_id_for_role, resolve_llm_test_route
from services.llm_router.types import LLMRequest, ModelRole


def test_summarizer_role_routes_to_deepseek_provider():
    assert provider_id_for_role(ModelRole.SUMMARIZER) == "deepseek"


def test_fast_worker_role_routes_to_deepseek_provider():
    assert provider_id_for_role(ModelRole.FAST_WORKER) == "deepseek"


def test_cheap_bulk_summary_test_route_uses_deepseek():
    role, provider_id = resolve_llm_test_route("cheap_bulk_summary")

    assert role == ModelRole.SUMMARIZER
    assert provider_id == "deepseek"


def test_orchestrator_test_route_resolves_to_fable_dry_run_route():
    role, provider_id = resolve_llm_test_route("orchestrator")

    assert role == ModelRole.ORCHESTRATOR
    assert provider_id == "fable"


def test_deepseek_provider_dry_run_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.deepseek.local")

    provider = DeepSeekProvider()
    response = provider.chat(LLMRequest(role=ModelRole.SUMMARIZER, prompt="summarize this"))

    assert response.provider_id == "deepseek"
    assert response.dry_run is True
    assert response.content == "[dry-run:deepseek] summarize this"
    assert response.metadata["base_url"] == "https://example.deepseek.local"
    assert response.metadata["reason"] == "DEEPSEEK_API_KEY is not configured"
    assert "api_key" not in response.metadata


def test_deepseek_provider_uses_mocked_chat_completion(monkeypatch):
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
                                "content": "mock summary",
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

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.deepseek.local")
    monkeypatch.setattr("services.llm_router.providers.deepseek.urllib_request.urlopen", mock_urlopen)

    provider = DeepSeekProvider(timeout_seconds=7)
    response = provider.chat(LLMRequest(role=ModelRole.SUMMARIZER, prompt="summarize this"))

    assert response.dry_run is False
    assert response.content == "mock summary"
    assert response.metadata["role"] == "summarizer"
    assert response.metadata["finish_reason"] == "stop"
    assert response.metadata["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }
    assert captured["authorization"] == "Bearer test-key-not-real"
    assert captured["body"]["messages"][-1] == {
        "role": "user",
        "content": "summarize this",
    }
    assert captured["timeout"] == 7
