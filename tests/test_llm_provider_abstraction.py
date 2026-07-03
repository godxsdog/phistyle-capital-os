from pathlib import Path

from services.llm_router.config import load_yaml_config
from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.providers.fable import FableProvider
from services.llm_router.types import LLMRequest, MessageRole, ModelRole
from services.llm_router.usage import usage_from_response


def test_deepseek_openai_compatible_message_normalization():
    provider = DeepSeekProvider(api_key="")

    normalized = provider.normalize_request(
        LLMRequest(role=ModelRole.SUMMARIZER, prompt="summarize this")
    )

    assert normalized.metadata["wire_api"] == "openai_compatible_chat"
    assert normalized.messages[0].role == MessageRole.SYSTEM
    assert normalized.messages[1].role == MessageRole.USER
    assert normalized.messages[1].content == "summarize this"


def test_fable_system_prompt_normalization_keeps_thinking_out_of_history():
    provider = FableProvider(api_key="")

    normalized = provider.normalize_request(
        LLMRequest(role=ModelRole.ORCHESTRATOR, prompt="decide this")
    )

    assert normalized.metadata["wire_api"] == "fable_chat"
    assert normalized.metadata["adaptive_thinking"] == "cannot_be_disabled"
    assert normalized.messages[0].role == MessageRole.SYSTEM
    assert all(message.role != MessageRole.REASONING for message in normalized.messages)


def test_fable_reasoning_block_is_separated_from_normal_content():
    provider = FableProvider(api_key="")
    normalized = provider.normalize_request(
        LLMRequest(role=ModelRole.ORCHESTRATOR, prompt="decide this")
    )

    response = provider.normalize_response(
        {
            "choices": [
                {
                    "message": {
                        "content": "final answer",
                        "thinking": "private reasoning",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "reasoning_tokens": 12,
            },
        },
        normalized,
    )

    assert response.content == "final answer"
    assert response.reasoning_content == "private reasoning"
    assert response.metadata["thinking_policy"] == "separate_or_discard"
    usage = usage_from_response(response, role=ModelRole.ORCHESTRATOR, agent_id="agent")
    assert usage.reasoning_tokens == 12


def test_routing_config_loads_from_yaml():
    config = load_yaml_config(Path("config/llm_routing.yaml"))

    assert config["routes"]["cheap_bulk_summary"]["provider"] == "deepseek"
    assert config["routes"]["high_risk_architecture"]["provider"] == "fable"


def test_provider_config_has_retry_and_fable_thinking_notes():
    config = load_yaml_config(Path("config/llm_providers.yaml"))

    assert config["providers"]["deepseek"]["retry"]["max_attempts"] == 2
    assert "adaptive thinking cannot be disabled" in config["providers"]["fable"]["notes"]

