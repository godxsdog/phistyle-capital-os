from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.llm_router.router import LLMRouter


@dataclass(frozen=True)
class AgentRunContext:
    run_id: str
    llm_router: LLMRouter = field(default_factory=LLMRouter)
    metadata: dict[str, Any] = field(default_factory=dict)

