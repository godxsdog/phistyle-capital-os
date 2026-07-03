from services.llm_router.router import route_task
from services.llm_router.types import ModelRole, ProviderType, TaskClass
from services.llm_router.provider_registry import get_provider


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

    assert decision.provider_id in {"local_ollama", "local_vllm"}
    assert decision.local_only is True


def test_cheap_bulk_summary_prefers_local_ollama():
    decision = route_task(TaskClass.CHEAP_BULK_SUMMARY)
    provider = get_provider(decision.provider_id)

    assert decision.provider_id == "local_ollama"
    assert provider.provider_type == ProviderType.LOCAL_OLLAMA


def test_third_party_proxy_is_registered_for_public_low_risk_work_only():
    provider = get_provider("third_party_deepseek")

    assert provider.provider_type == ProviderType.THIRD_PARTY_PROXY
    assert provider.local_only is False
    assert ModelRole.SUMMARIZER in provider.roles


def test_speculative_serving_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_SPECULATIVE_SERVING", raising=False)

    decision = route_task(TaskClass.SPECULATIVE_SERVING)

    assert decision.provider_id == "speculative_serving"
    assert decision.enabled is False


def test_speculative_serving_requires_explicit_config(monkeypatch):
    monkeypatch.setenv("ENABLE_SPECULATIVE_SERVING", "true")

    decision = route_task(TaskClass.SPECULATIVE_SERVING)

    assert decision.provider_id == "speculative_serving"
    assert decision.enabled is True
