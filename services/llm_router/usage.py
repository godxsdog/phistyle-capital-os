from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from services.llm_router.config import load_pricing_config
from services.llm_router.types import ModelRole, NormalizedLLMResponse, UsageRecord


def usage_from_response(
    response: NormalizedLLMResponse,
    role: ModelRole,
    agent_id: str | None = None,
    estimated_cost: float | None = None,
) -> UsageRecord:
    usage = response.metadata.get("usage", {})
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    reasoning_tokens = int(usage.get("reasoning_tokens", 0) or 0)
    return UsageRecord(
        request_id=str(uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=response.provider_id,
        model=response.model,
        role=role,
        agent_id=agent_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        estimated_cost=estimated_cost if estimated_cost is not None else estimate_cost(
            response.provider_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        ),
    )


def estimate_cost(
    provider: str,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
) -> float:
    pricing = load_pricing_config()["providers"][provider]
    return (
        input_tokens * float(pricing["input_per_million"])
        + output_tokens * float(pricing["output_per_million"])
        + reasoning_tokens * float(pricing["reasoning_per_million"])
    ) / 1_000_000
