from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable
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


class CodeReviewAgent:
    metadata = AgentMetadata(
        id="code-review-agent",
        name="Code Review Agent",
        role="reviewer",
        description="Reviews code changes and returns advisory-only recommendations.",
    )
    valid_scopes = {"backend", "frontend", "llm_router", "docs"}
    valid_risk_levels = {"low", "medium", "high"}
    secret_patterns = (
        re.compile(r"sk-ant-"),
        re.compile(r"sk-"),
        re.compile(r"API_KEY="),
        re.compile(r"-----BEGIN PRIVATE KEY-----"),
    )
    provider_names = ("deepseek", "fable", "openai", "ollama")

    def __init__(self, call_llm: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> None:
        self.call_llm = call_llm or self._stub_call_llm

    def run(self, input_data: dict[str, Any], context: AgentRunContext) -> AgentRunResult:
        now = datetime.utcnow()
        diff = str(input_data.get("diff", ""))
        scope = str(input_data.get("scope", ""))
        risk_level = str(input_data.get("risk_level", ""))
        llm_review = self._normalized_llm_review(
            self.call_llm(
                {
                    "diff": diff,
                    "scope": scope,
                    "risk_level": risk_level,
                }
            )
        )
        critical_issues = list(llm_review["critical_issues"])
        test_gaps = list(llm_review["test_gaps"])

        invalid_notes = self._validation_notes(scope, risk_level)
        if invalid_notes:
            critical_issues.extend(invalid_notes)

        has_secrets = self._contains_secret(diff)
        has_provider_logic_outside_adapters = self._has_provider_logic_outside_adapters(diff)
        has_test_gap = self._has_behavior_change_without_tests(diff)
        if has_test_gap:
            test_gaps.append("Behavior change detected without an accompanying tests/ change.")

        recommendation = self._recommendation(
            invalid_notes=invalid_notes,
            has_secrets=has_secrets,
            has_provider_logic_outside_adapters=has_provider_logic_outside_adapters,
            has_test_gap=has_test_gap,
            risk_level=risk_level,
        )
        return AgentRunResult(
            agent_id=self.metadata.id,
            status="success",
            output={
                "summary": llm_review["summary"],
                "critical_issues": critical_issues,
                "medium_issues": llm_review["medium_issues"],
                "low_issues": llm_review["low_issues"],
                "architecture_risks": llm_review["architecture_risks"],
                "security_risks": llm_review["security_risks"],
                "test_gaps": test_gaps,
                "recommendation": recommendation,
            },
            run_id=context.run_id,
            started_at=now,
            finished_at=datetime.utcnow(),
            metadata={
                "role": self.metadata.role,
                "advisory_only": True,
            },
        )

    def _stub_call_llm(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": "Stub code review response. Real Gemini review is not wired yet.",
            "critical_issues": [],
            "medium_issues": [],
            "low_issues": [],
            "architecture_risks": [],
            "security_risks": [],
            "test_gaps": [],
        }

    def _normalized_llm_review(self, review: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": review.get("summary", ""),
            "critical_issues": self._string_list_or_empty(review.get("critical_issues")),
            "medium_issues": self._string_list_or_empty(review.get("medium_issues")),
            "low_issues": self._string_list_or_empty(review.get("low_issues")),
            "architecture_risks": self._string_list_or_empty(review.get("architecture_risks")),
            "security_risks": self._string_list_or_empty(review.get("security_risks")),
            "test_gaps": self._string_list_or_empty(review.get("test_gaps")),
        }

    def _validation_notes(self, scope: str, risk_level: str) -> list[str]:
        notes = []
        if scope not in self.valid_scopes:
            notes.append(f"Invalid scope: {scope}")
        if risk_level not in self.valid_risk_levels:
            notes.append(f"Invalid risk_level: {risk_level}")
        return notes

    def _contains_secret(self, diff: str) -> bool:
        return any(pattern.search(diff) for pattern in self.secret_patterns)

    def _has_provider_logic_outside_adapters(self, diff: str) -> bool:
        provider_name_present = any(name in diff.lower() for name in self.provider_names)
        if not provider_name_present:
            return False
        return any(not self._is_adapter_or_provider_path(path) for path in self._changed_paths(diff))

    def _has_behavior_change_without_tests(self, diff: str) -> bool:
        paths = self._changed_paths(diff)
        if not paths:
            return False
        touches_behavior = any(
            not self._is_test_path(path) and not self._is_doc_path(path)
            for path in paths
        )
        touches_tests = any(self._is_test_path(path) for path in paths)
        return touches_behavior and not touches_tests

    def _recommendation(
        self,
        *,
        invalid_notes: list[str],
        has_secrets: bool,
        has_provider_logic_outside_adapters: bool,
        has_test_gap: bool,
        risk_level: str,
    ) -> str:
        if invalid_notes:
            return "request_changes"
        if has_secrets:
            return "request_changes"
        if has_provider_logic_outside_adapters:
            return "request_changes"
        if risk_level == "high":
            return "escalate_to_fable"
        if has_test_gap:
            return "request_changes"
        return "approve"

    def _changed_paths(self, diff: str) -> set[str]:
        paths: set[str] = set()
        for line in diff.splitlines():
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    paths.add(self._clean_diff_path(parts[3]))
            elif line.startswith("+++ "):
                path = line.removeprefix("+++ ").strip()
                if path != "/dev/null":
                    paths.add(self._clean_diff_path(path))
        return {path for path in paths if path}

    def _clean_diff_path(self, path: str) -> str:
        if path.startswith("a/") or path.startswith("b/"):
            return path[2:]
        return path

    def _is_adapter_or_provider_path(self, path: str) -> bool:
        parts = path.split("/")
        return "adapters" in parts or "providers" in parts

    def _is_test_path(self, path: str) -> bool:
        return path.startswith("tests/") or "/tests/" in path or path.endswith("_test.py")

    def _is_doc_path(self, path: str) -> bool:
        return path.startswith("docs/") or path.endswith(".md")

    def _string_list_or_empty(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]


class TriageAgent:
    metadata = AgentMetadata(
        id="triage-agent",
        name="Triage Agent",
        role="triage",
        description="Routes decision requests using deterministic advisory-only rules.",
    )
    engineering_escalation_keywords = (
        "security",
        "secret",
        "deployment",
        "database migration",
        "trading",
        "payment",
    )

    def run(self, input_data: dict[str, Any], context: AgentRunContext) -> AgentRunResult:
        now = datetime.utcnow()
        decision_request_id = int(input_data.get("decision_request_id"))
        question = str(input_data.get("question", ""))
        request_context = str(input_data.get("context", ""))
        decision_type = str(input_data.get("decision_type", ""))
        risk_level = str(input_data.get("risk_level", ""))

        recommendation, rationale, flags = self._triage(
            question=question,
            context=request_context,
            decision_type=decision_type,
            risk_level=risk_level,
        )
        return AgentRunResult(
            agent_id=self.metadata.id,
            status="success",
            output={
                "decision_request_id": decision_request_id,
                "risk_level": risk_level,
                "recommendation": recommendation,
                "rationale": rationale,
                "flags": flags,
            },
            run_id=context.run_id,
            started_at=now,
            finished_at=datetime.utcnow(),
            metadata={
                "role": self.metadata.role,
                "advisory_only": True,
                "risk_level_passthrough": True,
            },
        )

    def _triage(
        self,
        *,
        question: str,
        context: str,
        decision_type: str,
        risk_level: str,
    ) -> tuple[str, str, list[str]]:
        if not question.strip() or not context.strip():
            return (
                "reject_request",
                "Question and context are required before triage can classify the request.",
                ["empty-request"],
            )
        if risk_level == "high":
            return (
                "escalate_to_brain",
                "High risk decision requests should be escalated to the future Brain.",
                [decision_type, "high-risk"],
            )
        if decision_type in {"investment", "medical"}:
            informational_only = risk_level == "low" and "informational only" in context.lower()
            if not informational_only:
                return (
                    "escalate_to_brain",
                    "Investment and medical decision requests require Brain review unless low-risk and informational only.",
                    [decision_type],
                )
        if decision_type == "engineering" and self._contains_engineering_escalation_keyword(question, context):
            return (
                "escalate_to_brain",
                "Engineering request contains a sensitive operational keyword.",
                ["engineering", "sensitive-keyword"],
            )
        if risk_level == "medium":
            return (
                "use_worker_model",
                "Medium risk request can be prepared by a worker model before any future review.",
                ["medium-risk"],
            )
        return (
            "handle_locally",
            "Low risk request can be handled locally.",
            ["low-risk"],
        )

    def _contains_engineering_escalation_keyword(self, question: str, context: str) -> bool:
        haystack = f"{question}\n{context}".lower()
        return any(keyword in haystack for keyword in self.engineering_escalation_keywords)


class BrainOrchestrator:
    metadata = AgentMetadata(
        id="brain-orchestrator",
        name="Brain Orchestrator",
        role="brain",
        description="Produces deterministic advisory brain reviews for triaged decisions.",
    )

    def run(self, input_data: dict[str, Any], context: AgentRunContext) -> AgentRunResult:
        now = datetime.utcnow()
        decision_request_id = int(input_data.get("decision_request_id"))
        triage_result_id = input_data.get("triage_result_id")
        question = str(input_data.get("question", ""))
        request_context = str(input_data.get("context", ""))
        risk_level = str(input_data.get("risk_level", ""))
        triage_recommendation = input_data.get("triage_recommendation")

        recommendation, rationale, confidence, risks = self._review(
            triage_result_id=triage_result_id,
            triage_recommendation=triage_recommendation,
            question=question,
            context=request_context,
            risk_level=risk_level,
        )
        return AgentRunResult(
            agent_id=self.metadata.id,
            status="success",
            output={
                "decision_request_id": decision_request_id,
                "triage_result_id": triage_result_id,
                "recommendation": recommendation,
                "rationale": rationale,
                "confidence": confidence,
                "risks": risks,
                "required_human_approval": True,
            },
            run_id=context.run_id,
            started_at=now,
            finished_at=datetime.utcnow(),
            metadata={
                "role": self.metadata.role,
                "advisory_only": True,
                "deterministic_stub": True,
            },
        )

    def _review(
        self,
        *,
        triage_result_id: Any,
        triage_recommendation: Any,
        question: str,
        context: str,
        risk_level: str,
    ) -> tuple[str, str, str, list[str]]:
        if triage_result_id is None or triage_recommendation is None:
            return (
                "human_review_required",
                "Triage is required before a brain review can meaningfully proceed.",
                "high",
                ["missing-triage"],
            )
        if triage_recommendation == "reject_request":
            return (
                "reject",
                "Triage rejected the request, so BrainReview surfaces rejection for human review.",
                "medium",
                ["triage-rejected"],
            )
        if not question.strip() or not context.strip():
            return (
                "request_more_context",
                "Question and context are required before a useful brain review can proceed.",
                "high",
                ["missing-context"],
            )
        if triage_recommendation == "escalate_to_brain":
            return (
                "human_review_required",
                "Triage escalated this request to Brain review.",
                "medium",
                ["triage-escalated"],
            )
        if risk_level == "high":
            return (
                "human_review_required",
                "High risk requests require human review.",
                "medium",
                ["high-risk"],
            )
        if triage_recommendation == "use_worker_model":
            return (
                "defer",
                "Worker model preparation should happen before final human review.",
                "medium",
                ["worker-model-needed"],
            )
        return (
            "proceed",
            "No deterministic blocker found in this scaffold.",
            "low",
            ["low-risk"],
        )


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
    registry.register(CodeReviewAgent())
    registry.register(TriageAgent())
    registry.register(BrainOrchestrator())
    return AgentRuntime(registry=registry)


default_runtime = create_default_runtime()


def list_agents() -> list[dict[str, str]]:
    return default_runtime.list_agents()


def run_agent(agent_id: str, input_data: dict[str, Any]) -> AgentRunResult:
    return default_runtime.run_agent(agent_id, input_data)


__all__ = [
    "AgentRuntime",
    "BrainOrchestrator",
    "CodeReviewAgent",
    "DailyBriefAgent",
    "EchoAgent",
    "TriageAgent",
    "UnknownAgentError",
    "create_default_runtime",
    "default_runtime",
    "list_agents",
    "run_agent",
]
