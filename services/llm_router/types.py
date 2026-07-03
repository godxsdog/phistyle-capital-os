from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelRole(str, Enum):
    BRAIN = "brain"
    WORKER = "worker"
    TOOLS = "tools"
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


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    REASONING = "reasoning"


class ContentBlockType(str, Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    REFUSAL = "refusal"


class UnifiedFinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALL = "tool_call"
    REFUSAL = "refusal"
    ERROR = "error"
    UNKNOWN = "unknown"


class TaskClass(str, Enum):
    HIGH_RISK_ARCHITECTURE = "high_risk_architecture"
    FINAL_DECISION = "final_decision"
    INVESTMENT_THESIS = "investment_thesis"
    MULTI_AGENT_ARBITRATION = "multi_agent_arbitration"
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


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ContentBlock:
    type: ContentBlockType
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnifiedMessage:
    role: MessageRole
    content: tuple[ContentBlock, ...]
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def text(cls, role: MessageRole, text: str, name: str | None = None) -> "UnifiedMessage":
        return cls(role=role, content=(ContentBlock(type=ContentBlockType.TEXT, text=text),), name=name)

    @property
    def text_content(self) -> str:
        return "".join(block.text for block in self.content if block.type == ContentBlockType.TEXT)


# Backward-compatible alias used by earlier scaffolding.
Message = UnifiedMessage


@dataclass(frozen=True)
class LLMRequest:
    role: ModelRole
    prompt: str
    messages: tuple[ChatMessage, ...] = ()
    model: str | None = None


@dataclass(frozen=True)
class UnifiedRequest:
    role: ModelRole
    model: str
    messages: tuple[UnifiedMessage, ...]
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedLLMRequest(UnifiedRequest):
    pass


@dataclass(frozen=True)
class UnifiedUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass(frozen=True)
class UnifiedResponse:
    provider_id: str
    model: str
    role: ModelRole
    content: tuple[ContentBlock, ...]
    thinking: tuple[ContentBlock, ...] = ()
    tool_calls: tuple[dict[str, Any], ...] = ()
    finish_reason: UnifiedFinishReason = UnifiedFinishReason.UNKNOWN
    usage: UnifiedUsage = field(default_factory=UnifiedUsage)
    raw_response: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text_content(self) -> str:
        return "".join(block.text for block in self.content if block.type == ContentBlockType.TEXT)

    @property
    def reasoning_content(self) -> str | None:
        text = "".join(block.text for block in self.thinking if block.type == ContentBlockType.THINKING)
        return text or None


@dataclass(frozen=True)
class ProviderRefusal:
    provider_id: str
    model: str
    role: ModelRole
    reason: str
    retryable: bool = False
    finish_reason: UnifiedFinishReason = UnifiedFinishReason.REFUSAL
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedLLMResponse(UnifiedResponse):
    pass


@dataclass(frozen=True)
class UnifiedStreamEvent:
    event_type: str
    content_delta: str = ""
    reasoning_delta: str = ""
    stop_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedStreamEvent(UnifiedStreamEvent):
    pass


@dataclass(frozen=True)
class LLMResponse:
    provider_id: str
    model: str
    content: str
    dry_run: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class UsageRecord:
    request_id: str
    timestamp: str
    provider: str
    model: str
    role: ModelRole
    agent_id: str | None
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    estimated_cost: float | None
