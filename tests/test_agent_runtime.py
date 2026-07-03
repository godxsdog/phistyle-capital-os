import pytest

from phistyle_platform.runtime.runtime import create_default_runtime
from phistyle_platform.runtime.types import UnknownAgentError


def test_list_agents_includes_echo_agent():
    runtime = create_default_runtime()

    agents = runtime.list_agents()

    assert agents == [
        {
            "id": "echo-agent",
            "name": "Echo Agent",
            "role": "test",
            "description": "Returns the input message with echo metadata.",
        }
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

