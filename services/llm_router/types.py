from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    DEEP_REASONER = "deep_reasoner"
    CODER = "coder"
    FAST_WORKER = "fast_worker"
    SUMMARIZER = "summarizer"
    REVIEWER = "reviewer"


class ProviderType(str, Enum):
    FABLE = "fable"
    DEEPSEEK = "deepseek"
    CODEX = "codex"
    MINI = "mini"
    OPENAI = "openai"
    LOCAL_OLLAMA = "local_ollama"
    LOCAL_VLLM = "local_vllm"
    LOCAL_SGLANG = "local_sglang"
    THIRD_PARTY_PROXY = "third_party_proxy"
    SPECULATIVE_SERVING = "speculative_serving"


class TaskClass(str, Enum):
    HIGH_RISK_ARCHITECTURE = "high_risk_architecture"
    COMPLEX_REASONING = "complex_reasoning"
    CODE_IMPLEMENTATION = "code_implementation"
    DOCS_FORMATTING_SUMMARIES = "docs_formatting_summaries"
    LOCAL_PRIVATE_DATA = "local_private_data"
    CHEAP_BULK_SUMMARY = "cheap_bulk_summary"
    SPECULATIVE_SERVING = "speculative_serving"


@dataclass(frozen=True)
class Provider:
    id: str
    provider_type: ProviderType
    label: str
    default_model: str
    roles: tuple[ModelRole, ...]
    local_only: bool = False
    api_key_env: str | None = None
    base_url_env: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    task_class: TaskClass
    role: ModelRole
    provider_id: str
    model: str
    reason: str
    local_only: bool = False
    enabled: bool = True
