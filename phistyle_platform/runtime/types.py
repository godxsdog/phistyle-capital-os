from __future__ import annotations

from typing import Any, Protocol

from shared.models.agent import AgentMetadata
from shared.models.run import AgentRunResult


class Agent(Protocol):
    metadata: AgentMetadata

    def run(self, input_data: dict[str, Any], context: "RuntimeContext") -> AgentRunResult:
        ...


class AgentRuntimeError(Exception):
    pass


class UnknownAgentError(AgentRuntimeError):
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Unknown agent_id: {agent_id}")


class RuntimeContext(Protocol):
    run_id: str

