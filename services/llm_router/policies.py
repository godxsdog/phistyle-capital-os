from services.llm_router.config import routing_config
from services.llm_router.types import ModelRole, TaskClass


def policy_for_task(task_class: TaskClass) -> tuple[ModelRole, str, str]:
    route = routing_config(task_class.value)
    return ModelRole(route["role"]), route["provider"], route["reason"]
