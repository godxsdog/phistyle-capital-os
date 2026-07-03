from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from phistyle_platform.runtime.context import AgentRunContext
from phistyle_platform.runtime.registry import AgentRegistry
from phistyle_platform.runtime.types import UnknownAgentError
from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.types import LLMRequest, ModelRole
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


class DailyBriefAgent:
    metadata = AgentMetadata(
        id="daily-brief-agent",
        name="Daily Brief Agent",
        role="summarizer",
        description="Summarizes provided text into a short structured brief.",
    )

    def run(self, input_data: dict[str, Any], context: AgentRunContext) -> AgentRunResult:
        now = datetime.utcnow()
        topic = str(input_data.get("topic", "")).strip()
        text = str(input_data.get("text", "")).strip()
        route = context.llm_router.route_role(ModelRole.SUMMARIZER)
        if route.provider_id != "deepseek":
            raise RuntimeError(f"Unsupported summarizer provider route: {route.provider_id}")

        prompt = (
            "Create a concise daily brief from the provided text.\n"
            "Return strict JSON only, with no markdown, no prose before or after the JSON.\n"
            "The JSON object must have exactly these keys:\n"
            '{ "summary": string, "key_points": string[], "risk_flags": string[] }\n'
            f"Topic: {topic}\n\n"
            f"Text:\n{text}\n\n"
            "Keep summary short. Include risk_flags only when the text contains explicit risks."
        )
        llm_response = DeepSeekProvider().chat(
            LLMRequest(role=ModelRole.SUMMARIZER, prompt=prompt)
        )
        brief = self._parse_brief_response(llm_response.content)
        return AgentRunResult(
            agent_id=self.metadata.id,
            status="success",
            output={
                "topic": topic,
                "summary": brief["summary"],
                "key_points": brief["key_points"],
                "risk_flags": brief["risk_flags"],
                "source": "manual_input",
            },
            run_id=context.run_id,
            started_at=now,
            finished_at=datetime.utcnow(),
            metadata={
                "role": self.metadata.role,
                "llm_role": ModelRole.SUMMARIZER.value,
                "provider_id": llm_response.provider_id,
                "model": llm_response.model,
                "dry_run": llm_response.dry_run,
            },
        )

    def _parse_brief_response(self, raw_response: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return self._fallback_brief(raw_response)

        if not isinstance(parsed, dict):
            return self._fallback_brief(raw_response)

        summary = parsed.get("summary")
        key_points = parsed.get("key_points")
        risk_flags = parsed.get("risk_flags")
        if not isinstance(summary, str):
            return self._fallback_brief(raw_response)

        return {
            "summary": summary,
            "key_points": self._string_list_or_empty(key_points),
            "risk_flags": self._string_list_or_empty(risk_flags),
        }

    def _fallback_brief(self, raw_response: str) -> dict[str, Any]:
        return {
            "summary": raw_response,
            "key_points": [],
            "risk_flags": [],
        }

    def _string_list_or_empty(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]


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
    registry.register(DailyBriefAgent())
    return AgentRuntime(registry=registry)


default_runtime = create_default_runtime()


def list_agents() -> list[dict[str, str]]:
    return default_runtime.list_agents()


def run_agent(agent_id: str, input_data: dict[str, Any]) -> AgentRunResult:
    return default_runtime.run_agent(agent_id, input_data)


__all__ = [
    "AgentRuntime",
    "DailyBriefAgent",
    "EchoAgent",
    "UnknownAgentError",
    "create_default_runtime",
    "default_runtime",
    "list_agents",
    "run_agent",
]
