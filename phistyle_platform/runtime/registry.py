from __future__ import annotations

from phistyle_platform.runtime.types import Agent, UnknownAgentError
from shared.models.agent import AgentMetadata


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.metadata.id] = agent

    def list_agents(self) -> list[AgentMetadata]:
        return [agent.metadata for agent in self._agents.values()]

    def list_agent_dicts(self) -> list[dict[str, str]]:
        return [metadata.to_dict() for metadata in self.list_agents()]

    def get(self, agent_id: str) -> Agent:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise UnknownAgentError(agent_id) from exc

