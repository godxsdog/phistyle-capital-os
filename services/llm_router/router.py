from __future__ import annotations

from services.llm_router.policies import policy_for_task
from services.llm_router.provider_registry import get_provider
from services.llm_router.types import RouteDecision, TaskClass


class LLMRouter:
    """Returns routing decisions only. It does not execute model calls."""

    def route(self, task_class: TaskClass | str) -> RouteDecision:
        task = TaskClass(task_class)
        role, provider_id, reason = policy_for_task(task)
        provider = get_provider(provider_id)
        return RouteDecision(
            task_class=task,
            role=role,
            provider_id=provider.id,
            model=provider.default_model,
            reason=reason,
            local_only=provider.local_only,
        )


def route_task(task_class: TaskClass | str) -> RouteDecision:
    return LLMRouter().route(task_class)
