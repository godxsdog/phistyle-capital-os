from __future__ import annotations

import os

from services.llm_router.config import first_matching_role_route
from services.llm_router.policies import policy_for_task
from services.llm_router.provider_registry import get_provider
from services.llm_router.types import ModelRole, RouteDecision, TaskClass


class LLMRouter:
    """Returns routing decisions only. It does not execute model calls."""

    def route(self, task_class: TaskClass | str) -> RouteDecision:
        task = TaskClass(task_class)
        role, provider_id, reason = policy_for_task(task)
        provider = get_provider(provider_id)
        enabled = True
        if task == TaskClass.SPECULATIVE_SERVING:
            enabled = os.getenv("ENABLE_SPECULATIVE_SERVING", "false").lower() == "true"
        return RouteDecision(
            task_class=task,
            role=role,
            provider_id=provider.id,
            model=provider.default_model,
            reason=reason,
            local_only=provider.local_only,
            enabled=enabled,
        )

    def route_role(self, role: ModelRole | str, context: dict | None = None) -> RouteDecision:
        return route_role(role, context)


def route_task(task_class: TaskClass | str) -> RouteDecision:
    return LLMRouter().route(task_class)


def provider_id_for_role(role: ModelRole | str) -> str:
    return route_role(role).provider_id


def route_role(role: ModelRole | str, context: dict | None = None) -> RouteDecision:
    model_role = ModelRole(role)
    route = first_matching_role_route(model_role.value, context)
    return RouteDecision(
        task_class=TaskClass.COMPLEX_REASONING,
        role=model_role,
        provider_id=route["provider"],
        model=route["model"],
        reason=route["reason"],
        enabled=True,
    )


def resolve_llm_test_route(route_name: str) -> tuple[ModelRole, str]:
    try:
        role = ModelRole(route_name)
        return role, provider_id_for_role(role)
    except ValueError:
        task = TaskClass(route_name)
        decision = route_task(task)
        return decision.role, decision.provider_id
