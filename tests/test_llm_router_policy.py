from services.llm_router.router import route_task
from services.llm_router.types import ModelRole, TaskClass


def test_high_risk_architecture_routes_to_fable_orchestrator():
    decision = route_task(TaskClass.HIGH_RISK_ARCHITECTURE)

    assert decision.provider_id == "fable"
    assert decision.role == ModelRole.ORCHESTRATOR


def test_code_implementation_routes_to_codex():
    decision = route_task(TaskClass.CODE_IMPLEMENTATION)

    assert decision.provider_id == "codex"
    assert decision.role == ModelRole.CODER


def test_private_data_routes_to_local_only_provider():
    decision = route_task(TaskClass.LOCAL_PRIVATE_DATA)

    assert decision.provider_id == "local"
    assert decision.local_only is True

