from __future__ import annotations

from typing import Any, Protocol

from services.llm_router.types import (
    LLMRequest,
    LLMResponse,
    NormalizedLLMRequest,
    NormalizedLLMResponse,
    NormalizedStreamEvent,
    ProviderRefusal,
)


class LLMProvider(Protocol):
    provider_id: str

    def normalize_request(self, request: LLMRequest) -> NormalizedLLMRequest:
        ...

    def call(self, normalized_request: NormalizedLLMRequest) -> dict[str, Any]:
        ...

    def normalize_response(
        self,
        raw_response: dict[str, Any],
        normalized_request: NormalizedLLMRequest,
    ) -> NormalizedLLMResponse | ProviderRefusal:
        ...

    def normalize_stream_event(self, raw_event: dict[str, Any]) -> NormalizedStreamEvent:
        ...

    def chat(self, request: LLMRequest) -> LLMResponse:
        ...
