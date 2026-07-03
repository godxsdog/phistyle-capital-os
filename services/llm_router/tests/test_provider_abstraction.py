from pathlib import Path

from services.llm_router.config import first_matching_role_route, load_yaml_config
from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.providers.fable import FableProvider
from services.llm_router.types import (
    ChatMessage,
    ContentBlockType,
    LLMRequest,
    MessageRole,
    ModelRole,
    ProviderRefusal,
    UnifiedFinishReason,
)


def test_deepseek_openai_compatible_message_normalization():
    provider = DeepSeekProvider(api_key="")

    normalized = provider.normalize_request(
        LLMRequest(role=ModelRole.WORKER, prompt="summarize this")
    )

    assert normalized.metadata["wire_api"] == "openai_compatible_chat"
    assert normalized.messages[0].role == MessageRole.SYSTEM
    assert normalized.messages[1].role == MessageRole.USER
    assert normalized.messages[1].text_content == "summarize this"


def test_fable_system_prompt_normalization_merges_multiple_system_messages():
    provider = FableProvider(api_key="")

    normalized = provider.normalize_request(
        LLMRequest(
            role=ModelRole.ORCHESTRATOR,
            prompt="ignored when messages exist",
            messages=(
                ChatMessage(role="system", content="system one"),
                ChatMessage(role="user", content="decide this"),
                ChatMessage(role="system", content="system two"),
            ),
        )
    )

    assert normalized.metadata["adaptive_thinking"] == "cannot_be_disabled"
    assert normalized.messages[0].role == MessageRole.SYSTEM
    assert normalized.messages[0].text_content == "system one\n\nsystem two"
    assert normalized.messages[1].role == MessageRole.USER


def test_thinking_block_separation_never_lands_in_conversation_history():
    provider = FableProvider(api_key="")
    normalized = provider.normalize_request(
        LLMRequest(
            role=ModelRole.ORCHESTRATOR,
            prompt="ignored when messages exist",
            messages=(
                ChatMessage(role="system", content="system"),
                ChatMessage(role="reasoning", content="private thinking"),
                ChatMessage(role="user", content="decide this"),
            ),
        )
    )

    assert all(message.role != MessageRole.REASONING for message in normalized.messages)

    response = provider.normalize_response(
        {
            "choices": [
                {
                    "message": {
                        "content": "final",
                        "thinking": "private thinking",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "reasoning_tokens": 3,
            },
        },
        normalized,
    )

    assert not isinstance(response, ProviderRefusal)
    assert response.content[0].type == ContentBlockType.TEXT
    assert response.thinking[0].type == ContentBlockType.THINKING
    assert response.thinking[0].text == "private thinking"


def test_stream_event_normalization_openai_delta_and_anthropic_delta_are_equivalent():
    deepseek = DeepSeekProvider(api_key="")
    fable = FableProvider(api_key="")

    openai_event = deepseek.normalize_stream_event(
        {"choices": [{"delta": {"content": "hello"}}]}
    )
    anthropic_like_event = fable.normalize_stream_event(
        {"choices": [{"delta": {"content": "hello"}}]}
    )

    assert openai_event.content_delta == anthropic_like_event.content_delta == "hello"
    assert openai_event.event_type == anthropic_like_event.event_type == "message_delta"


def test_routing_config_load_first_match_wins_and_fallback():
    config = load_yaml_config(Path("services/llm_router/config/llm_routing.yaml"))

    assert config["role_routes"][-1]["match"]["role"] == "*"
    assert first_matching_role_route("worker", {"task": "cheap_bulk_summary"})["provider"] == "deepseek"
    assert first_matching_role_route("worker", {"task": "unknown"})["provider"] == "deepseek"
    assert first_matching_role_route("unknown-role")["provider"] == "deepseek"


def test_refusal_is_non_retryable_result_not_generic_exception():
    provider = FableProvider(api_key="")
    normalized = provider.normalize_request(
        LLMRequest(role=ModelRole.ORCHESTRATOR, prompt="decide this")
    )

    result = provider.normalize_response(
        {
            "choices": [
                {
                    "message": {
                        "refusal": "cannot comply",
                    },
                    "finish_reason": "refusal",
                }
            ]
        },
        normalized,
    )

    assert isinstance(result, ProviderRefusal)
    assert result.retryable is False
    assert result.finish_reason == UnifiedFinishReason.REFUSAL

