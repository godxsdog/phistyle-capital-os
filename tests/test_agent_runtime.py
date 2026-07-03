import pytest

from phistyle_platform.runtime.runtime import create_default_runtime
from phistyle_platform.runtime.types import UnknownAgentError
from services.llm_router.types import LLMResponse


def test_list_agents_includes_default_agents():
    runtime = create_default_runtime()

    agents = runtime.list_agents()

    assert agents == [
        {
            "id": "echo-agent",
            "name": "Echo Agent",
            "role": "test",
            "description": "Returns the input message with echo metadata.",
        },
        {
            "id": "daily-brief-agent",
            "name": "Daily Brief Agent",
            "role": "summarizer",
            "description": "Summarizes provided text into a short structured brief.",
        },
    ]


def test_run_echo_agent_returns_message_and_metadata():
    runtime = create_default_runtime()

    result = runtime.run_agent("echo-agent", {"message": "hello"})

    assert result.agent_id == "echo-agent"
    assert result.status == "success"
    assert result.output == {
        "message": "hello",
        "echo": True,
    }
    assert result.metadata["llm_router_ready"] is True
    assert len(runtime.list_runs()) == 1


def test_invalid_agent_id_returns_clear_error():
    runtime = create_default_runtime()

    with pytest.raises(UnknownAgentError, match="Unknown agent_id: missing-agent"):
        runtime.run_agent("missing-agent", {"message": "hello"})


def test_run_daily_brief_agent_uses_summarizer_route(monkeypatch):
    runtime = create_default_runtime()

    def mock_chat(self, request):
        assert request.role.value == "summarizer"
        assert "Topic: AI infrastructure" in request.prompt
        assert "GPU clusters expanded" in request.prompt
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content=(
                '{"summary":"AI infrastructure demand remains strong.",'
                '"key_points":["GPU clusters expanded"],'
                '"risk_flags":["Power availability may constrain growth"]}'
            ),
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    result = runtime.run_agent(
        "daily-brief-agent",
        {
            "topic": "AI infrastructure",
            "text": "GPU clusters expanded across hyperscale data centers.",
        },
    )

    assert result.agent_id == "daily-brief-agent"
    assert result.status == "success"
    assert result.output == {
        "topic": "AI infrastructure",
        "summary": "AI infrastructure demand remains strong.",
        "key_points": ["GPU clusters expanded"],
        "risk_flags": ["Power availability may constrain growth"],
        "source": "manual_input",
    }
    assert result.metadata["llm_role"] == "summarizer"
    assert result.metadata["provider_id"] == "deepseek"


def test_run_daily_brief_agent_falls_back_when_response_is_not_json(monkeypatch):
    runtime = create_default_runtime()

    def mock_chat(self, request):
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content="AI infrastructure demand remains strong.",
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    result = runtime.run_agent(
        "daily-brief-agent",
        {
            "topic": "AI infrastructure",
            "text": "GPU clusters expanded across hyperscale data centers.",
        },
    )

    assert result.output == {
        "topic": "AI infrastructure",
        "summary": "AI infrastructure demand remains strong.",
        "key_points": [],
        "risk_flags": [],
        "source": "manual_input",
    }
