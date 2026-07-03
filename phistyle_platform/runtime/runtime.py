from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from phistyle_platform.runtime.context import AgentRunContext
from phistyle_platform.runtime.registry import AgentRegistry
from phistyle_platform.runtime.types import UnknownAgentError
from shared.models.agent import AgentMetadata
from shared.models.run import AgentRunResult


class EchoAgent:
    metadata = AgentMetadata(
        id="echo-agent",
        name="Echo Agent",
        role="test",
        description="Returns the input message with echo metadata.",
    )

    def run(self, input_data: dict[str, Any], context: AgentRunContext) -> AgentRunResult:
        now = datetime.utcnow()
        message = input_data.get("message", "")
        return AgentRunResult(
            agent_id=self.metadata.id,
            status="success",
            output={
                "message": message,
                "echo": True,
            },
            run_id=context.run_id,
            started_at=now,
            finished_at=now,
            metadata={
                "role": self.metadata.role,
                "llm_router_ready": context.llm_router is not None,
            },
        )


class AgentRuntime:
    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self.registry = registry or AgentRegistry()
        self._runs: list[AgentRunResult] = []

    def list_agents(self) -> list[dict[str, str]]:
        return self.registry.list_agent_dicts()

    def run_agent(self, agent_id: str, input_data: dict[str, Any]) -> AgentRunResult:
        agent = self.registry.get(agent_id)
        context = AgentRunContext(run_id=str(uuid4()))
        result = agent.run(input_data, context)
        self._runs.append(result)
        return result

    def list_runs(self) -> list[AgentRunResult]:
        return list(self._runs)


def create_default_runtime() -> AgentRuntime:
    registry = AgentRegistry()
    registry.register(EchoAgent())
    return AgentRuntime(registry=registry)


default_runtime = create_default_runtime()


def list_agents() -> list[dict[str, str]]:
    return default_runtime.list_agents()


def run_agent(agent_id: str, input_data: dict[str, Any]) -> AgentRunResult:
    return default_runtime.run_agent(agent_id, input_data)


__all__ = [
    "AgentRuntime",
    "EchoAgent",
    "UnknownAgentError",
    "create_default_runtime",
    "default_runtime",
    "list_agents",
    "run_agent",
]

