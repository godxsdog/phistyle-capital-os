from __future__ import annotations

import json
import os
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from services.llm_router.types import ChatMessage, LLMRequest, LLMResponse, ModelRole
from services.llm_router.types import (
    MessageRole,
    ContentBlock,
    ContentBlockType,
    NormalizedLLMRequest,
    NormalizedLLMResponse,
    NormalizedStreamEvent,
    ProviderRefusal,
    UnifiedFinishReason,
    UnifiedUsage,
    UnifiedMessage,
)


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


class DeepSeekProvider:
    provider_id = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        timeout_seconds: int = 30,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL)).rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def dry_run(self) -> bool:
        return not bool(self._api_key)

    def chat(self, request: LLMRequest) -> LLMResponse:
        normalized_request = self.normalize_request(request)
        model = normalized_request.model
        if self.dry_run:
            return LLMResponse(
                provider_id=self.provider_id,
                model=model,
                content=f"[dry-run:{self.provider_id}] {request.prompt}",
                dry_run=True,
                metadata={
                    "role": request.role.value,
                    "base_url": self.base_url,
                    "reason": "DEEPSEEK_API_KEY is not configured",
                },
            )

        response_payload = self.call(normalized_request)
        normalized_response = self.normalize_response(response_payload, normalized_request)
        if isinstance(normalized_response, ProviderRefusal):
            return LLMResponse(
                provider_id=self.provider_id,
                model=model,
                content=normalized_response.reason,
                dry_run=False,
                metadata={
                    "role": request.role.value,
                    "finish_reason": normalized_response.finish_reason.value,
                    "retryable": normalized_response.retryable,
                },
            )
        return LLMResponse(
            provider_id=self.provider_id,
            model=model,
            content=normalized_response.text_content,
            dry_run=False,
            metadata=normalized_response.metadata,
        )

    def normalize_request(self, request: LLMRequest) -> NormalizedLLMRequest:
        return NormalizedLLMRequest(
            role=request.role,
            model=request.model or self.model,
            messages=tuple(
                UnifiedMessage.text(role=MessageRole(message.role), text=message.content)
                for message in self._messages_for_request(request)
            ),
            max_tokens=None,
            metadata={"wire_api": "openai_compatible_chat"},
        )

    def call(self, normalized_request: NormalizedLLMRequest) -> dict:
        payload = {
            "model": normalized_request.model,
            "messages": [
                {"role": message.role.value, "content": message.text_content}
                for message in normalized_request.messages
                if message.role != MessageRole.REASONING
            ],
            "stream": False,
        }
        return self._post_chat_completion(payload)

    def normalize_response(
        self,
        raw_response: dict,
        normalized_request: NormalizedLLMRequest,
    ) -> NormalizedLLMResponse | ProviderRefusal:
        choice = raw_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = self._finish_reason(choice.get("finish_reason"))
        if finish_reason == UnifiedFinishReason.REFUSAL:
            return ProviderRefusal(
                provider_id=self.provider_id,
                model=normalized_request.model,
                role=normalized_request.role,
                reason=message.get("refusal") or message.get("content") or "provider refusal",
                metadata={"raw_finish_reason": choice.get("finish_reason")},
            )
        content = (
            message.get("content", "")
        )
        reasoning_content = message.get("reasoning_content") or message.get("thinking")
        usage = raw_response.get("usage", {})
        return NormalizedLLMResponse(
            provider_id=self.provider_id,
            model=normalized_request.model,
            role=normalized_request.role,
            content=(ContentBlock(type=ContentBlockType.TEXT, text=content),) if content else (),
            thinking=(ContentBlock(type=ContentBlockType.THINKING, text=reasoning_content),) if reasoning_content else (),
            finish_reason=finish_reason,
            usage=UnifiedUsage(
                input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage.get("completion_tokens", 0) or 0),
                reasoning_tokens=int(usage.get("reasoning_tokens", 0) or 0),
            ),
            tool_calls=tuple(message.get("tool_calls", []) or []),
            raw_response=raw_response,
            metadata={
                "role": normalized_request.role.value,
                "finish_reason": choice.get("finish_reason"),
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "reasoning_tokens": usage.get("reasoning_tokens", 0),
                },
            },
        )

    def normalize_stream_event(self, raw_event: dict) -> NormalizedStreamEvent:
        delta = raw_event.get("choices", [{}])[0].get("delta", {})
        return NormalizedStreamEvent(
            event_type="message_delta",
            content_delta=delta.get("content", "") or "",
            reasoning_delta=delta.get("reasoning_content", "") or delta.get("thinking", "") or "",
            stop_reason=raw_event.get("choices", [{}])[0].get("finish_reason"),
            metadata={"provider_id": self.provider_id},
        )

    def _finish_reason(self, raw_finish_reason: str | None) -> UnifiedFinishReason:
        if raw_finish_reason == "stop":
            return UnifiedFinishReason.STOP
        if raw_finish_reason == "length":
            return UnifiedFinishReason.LENGTH
        if raw_finish_reason in {"tool_calls", "function_call"}:
            return UnifiedFinishReason.TOOL_CALL
        if raw_finish_reason == "refusal":
            return UnifiedFinishReason.REFUSAL
        return UnifiedFinishReason.UNKNOWN

    def _messages_for_request(self, request: LLMRequest) -> tuple[ChatMessage, ...]:
        if request.messages:
            return request.messages
        return (
            ChatMessage(role="system", content=self._system_prompt_for_role(request.role)),
            ChatMessage(role="user", content=request.prompt),
        )

    def _system_prompt_for_role(self, role: ModelRole) -> str:
        if role == ModelRole.SUMMARIZER:
            return "You summarize low-risk text clearly and concisely."
        if role == ModelRole.FAST_WORKER:
            return "You handle low-risk text work quickly and concisely."
        return "You are a low-risk text assistant."

    def _post_chat_completion(self, payload: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib_request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"DeepSeek request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("DeepSeek request failed before receiving a response") from exc
