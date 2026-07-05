import json

import pytest

from phistyle_platform.runtime.runtime import BrainOrchestrator, CodeReviewAgent, TriageAgent, create_default_runtime
from phistyle_platform.runtime.types import UnknownAgentError
from services.llm_router.types import LLMResponse


@pytest.fixture(autouse=True)
def default_deepseek_dry_run(monkeypatch):
    def mock_chat(self, request):
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content="[dry-run:deepseek] missing api key",
            dry_run=True,
            metadata={},
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )


def stub_review(**overrides):
    review = {
        "summary": "LLM review summary.",
        "critical_issues": [],
        "medium_issues": [],
        "low_issues": [],
        "architecture_risks": [],
        "security_risks": [],
        "test_gaps": [],
    }
    review.update(overrides)
    return review


def run_code_review(diff, scope="backend", risk_level="low", review=None):
    agent = CodeReviewAgent(call_llm=lambda request: review or stub_review())
    result = agent.run(
        {
            "diff": diff,
            "scope": scope,
            "risk_level": risk_level,
        },
        context=type("Context", (), {"run_id": "test-run"})(),
    )
    return result.output


def test_list_agents_includes_default_agents():
    runtime = create_default_runtime()

    agents = runtime.list_agents()

    assert agents == [
        {
            "id": "echo-agent",
            "name": "Echo Agent",
            "role": "test",
            "description": "Returns the input message with echo metadata.",
        },
        {
            "id": "daily-brief-agent",
            "name": "Daily Brief Agent",
            "role": "summarizer",
            "description": "Summarizes provided text into a short structured brief.",
        },
        {
            "id": "code-review-agent",
            "name": "Code Review Agent",
            "role": "reviewer",
            "description": "Reviews code changes and returns advisory-only recommendations.",
        },
        {
            "id": "triage-agent",
            "name": "Triage Agent",
            "role": "triage",
            "description": "Routes decision requests using deterministic advisory-only rules.",
        },
        {
            "id": "brain-orchestrator",
            "name": "Brain Orchestrator",
            "role": "brain",
            "description": "Produces advisory brain reviews for triaged decisions.",
        },
    ]


def test_run_echo_agent_returns_message_and_metadata():
    runtime = create_default_runtime()

    result = runtime.run_agent("echo-agent", {"message": "hello"})

    assert result.agent_id == "echo-agent"
    assert result.status == "success"
    assert result.output == {
        "message": "hello",
        "echo": True,
    }
    assert result.metadata["llm_router_ready"] is True
    assert len(runtime.list_runs()) == 1


def test_invalid_agent_id_returns_clear_error():
    runtime = create_default_runtime()

    with pytest.raises(UnknownAgentError, match="Unknown agent_id: missing-agent"):
        runtime.run_agent("missing-agent", {"message": "hello"})


def test_run_daily_brief_agent_uses_summarizer_route(monkeypatch):
    runtime = create_default_runtime()

    def mock_chat(self, request):
        assert request.role.value == "summarizer"
        assert "Topic: AI infrastructure" in request.prompt
        assert "GPU clusters expanded" in request.prompt
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content=(
                '{"summary":"AI infrastructure demand remains strong.",'
                '"key_points":["GPU clusters expanded"],'
                '"risk_flags":["Power availability may constrain growth"]}'
            ),
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    result = runtime.run_agent(
        "daily-brief-agent",
        {
            "topic": "AI infrastructure",
            "text": "GPU clusters expanded across hyperscale data centers.",
        },
    )

    assert result.agent_id == "daily-brief-agent"
    assert result.status == "success"
    assert result.output == {
        "topic": "AI infrastructure",
        "summary": "AI infrastructure demand remains strong.",
        "key_points": ["GPU clusters expanded"],
        "risk_flags": ["Power availability may constrain growth"],
        "source": "manual_input",
    }
    assert result.metadata["llm_role"] == "summarizer"
    assert result.metadata["provider_id"] == "deepseek"


def test_run_daily_brief_agent_falls_back_when_response_is_not_json(monkeypatch):
    runtime = create_default_runtime()

    def mock_chat(self, request):
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content="AI infrastructure demand remains strong.",
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    result = runtime.run_agent(
        "daily-brief-agent",
        {
            "topic": "AI infrastructure",
            "text": "GPU clusters expanded across hyperscale data centers.",
        },
    )

    assert result.output == {
        "topic": "AI infrastructure",
        "summary": "AI infrastructure demand remains strong.",
        "key_points": [],
        "risk_flags": [],
        "source": "manual_input",
    }


def test_code_review_agent_secrets_request_changes_regardless_of_risk_level():
    output = run_code_review(
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "+DEEPSEEK_API_KEY=sk-test",
        risk_level="low",
    )

    assert output["summary"] == "LLM review summary."
    assert output["recommendation"] == "request_changes"


def test_code_review_agent_provider_logic_outside_adapters_requests_changes():
    output = run_code_review(
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "+provider = 'deepseek'",
    )

    assert output["recommendation"] == "request_changes"


def test_code_review_agent_high_risk_escalates_to_fable_when_no_other_issues():
    output = run_code_review(
        "diff --git a/docs/readme.md b/docs/readme.md\n"
        "+++ b/docs/readme.md\n"
        "+Documentation update.",
        scope="docs",
        risk_level="high",
    )

    assert output["recommendation"] == "escalate_to_fable"


def test_code_review_agent_behavior_change_without_tests_requests_changes():
    output = run_code_review(
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "+def new_endpoint():\n"
        "+    return {'status': 'ok'}",
    )

    assert output["recommendation"] == "request_changes"
    assert output["test_gaps"] == [
        "Behavior change detected without an accompanying tests/ change."
    ]


def test_code_review_agent_clean_low_risk_diff_approves():
    output = run_code_review(
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "+def new_endpoint():\n"
        "+    return {'status': 'ok'}\n"
        "diff --git a/tests/test_main.py b/tests/test_main.py\n"
        "+++ b/tests/test_main.py\n"
        "+def test_new_endpoint():\n"
        "+    assert True",
    )

    assert output["recommendation"] == "approve"


def test_code_review_agent_invalid_scope_or_risk_level_requests_changes():
    output = run_code_review(
        "diff --git a/docs/readme.md b/docs/readme.md\n"
        "+++ b/docs/readme.md\n"
        "+Documentation update.",
        scope="unknown",
        risk_level="extreme",
    )

    assert output["recommendation"] == "request_changes"
    assert output["critical_issues"] == [
        "Invalid scope: unknown",
        "Invalid risk_level: extreme",
    ]


def test_code_review_agent_secrets_win_over_high_risk_escalation():
    output = run_code_review(
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "+token = 'sk-ant-secret'",
        risk_level="high",
    )

    assert output["recommendation"] == "request_changes"


def run_triage_agent(
    *,
    question="Should I reduce exposure?",
    context="Position is concentrated.",
    decision_type="investment",
    risk_level="low",
):
    agent = TriageAgent()
    result = agent.run(
        {
            "decision_request_id": 1,
            "question": question,
            "context": context,
            "decision_type": decision_type,
            "risk_level": risk_level,
        },
        context=type("Context", (), {"run_id": "test-run"})(),
    )
    return result.output


def test_triage_agent_empty_question_or_context_rejects_before_high_risk():
    output = run_triage_agent(
        question=" ",
        context="Medical high risk context.",
        decision_type="investment",
        risk_level="high",
    )

    assert output["risk_level"] == "high"
    assert output["recommendation"] == "reject_request"


def test_triage_agent_high_risk_escalates_to_brain():
    output = run_triage_agent(decision_type="travel", risk_level="high")

    assert output["recommendation"] == "escalate_to_brain"


def test_triage_agent_investment_high_risk_escalates_to_brain():
    output = run_triage_agent(decision_type="investment", risk_level="high")

    assert output["recommendation"] == "escalate_to_brain"


def test_triage_agent_investment_low_risk_informational_only_falls_through():
    output = run_triage_agent(
        decision_type="investment",
        risk_level="low",
        context="This is INFORMATIONAL ONLY and does not require a portfolio action.",
    )

    assert output["recommendation"] == "handle_locally"


def test_triage_agent_engineering_sensitive_keyword_escalates_to_brain():
    output = run_triage_agent(
        decision_type="engineering",
        risk_level="low",
        question="Should we change deployment settings?",
        context="Routine backend change.",
    )

    assert output["recommendation"] == "escalate_to_brain"


def test_triage_agent_medium_risk_uses_worker_model():
    output = run_triage_agent(decision_type="travel", risk_level="medium")

    assert output["recommendation"] == "use_worker_model"


def test_triage_agent_low_risk_handles_locally():
    output = run_triage_agent(decision_type="travel", risk_level="low")

    assert output["recommendation"] == "handle_locally"


def run_brain_orchestrator(
    *,
    triage_result_id=1,
    triage_recommendation="handle_locally",
    question="Should we proceed?",
    context="Context is available.",
    risk_level="low",
):
    agent = BrainOrchestrator()
    result = agent.run(
        {
            "decision_request_id": 1,
            "triage_result_id": triage_result_id,
            "question": question,
            "context": context,
            "risk_level": risk_level,
            "triage_recommendation": triage_recommendation,
        },
        context=type("Context", (), {"run_id": "test-run"})(),
    )
    return result.output


def valid_brain_review_response(**overrides):
    payload = {
        "recommendation": "human_review_required",
        "rationale": "LLM review challenges the thesis and names concentration risk.",
        "confidence": "high",
        "risks": ["concentration", "missing-evidence"],
    }
    payload.update(overrides)
    return LLMResponse(
        provider_id="deepseek",
        model="deepseek-reasoner",
        content=json.dumps(payload),
        dry_run=False,
        metadata={},
    )


def test_brain_orchestrator_missing_triage_uses_rule_zero():
    output = run_brain_orchestrator(triage_result_id=None, triage_recommendation=None)

    assert output["recommendation"] == "human_review_required"
    assert output["confidence"] == "high"
    assert output["required_human_approval"] is True


def test_brain_orchestrator_reject_request_wins_over_missing_context():
    output = run_brain_orchestrator(
        triage_recommendation="reject_request",
        context="",
    )

    assert output["recommendation"] == "reject"
    assert output["confidence"] == "medium"


def test_brain_orchestrator_missing_context_requests_more_context():
    output = run_brain_orchestrator(context="")

    assert output["recommendation"] == "request_more_context"
    assert output["confidence"] == "high"


def test_brain_orchestrator_escalate_to_brain_requires_human_review():
    output = run_brain_orchestrator(triage_recommendation="escalate_to_brain")

    assert output["recommendation"] == "human_review_required"
    assert output["confidence"] == "medium"


def test_brain_orchestrator_high_risk_requires_human_review():
    output = run_brain_orchestrator(risk_level="high")

    assert output["recommendation"] == "human_review_required"
    assert output["confidence"] == "medium"


def test_brain_orchestrator_worker_model_defers():
    output = run_brain_orchestrator(triage_recommendation="use_worker_model")

    assert output["recommendation"] == "defer"
    assert output["confidence"] == "medium"


def test_brain_orchestrator_clean_low_risk_proceeds_but_still_requires_human_approval():
    output = run_brain_orchestrator()

    assert output["recommendation"] == "proceed"
    assert output["confidence"] == "low"
    assert output["required_human_approval"] is True


def test_brain_orchestrator_valid_llm_json_can_replace_proceed_recommendation(monkeypatch):
    def mock_chat(self, request):
        assert request.role.value == "deep_reasoner"
        return valid_brain_review_response(
            recommendation="human_review_required",
            risks=["concentration, liquidity", "missing-evidence"],
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    output = run_brain_orchestrator()

    assert output["recommendation"] == "human_review_required"
    assert output["rationale"] == "LLM review challenges the thesis and names concentration risk."
    assert output["confidence"] == "high"
    assert output["risks"] == ["concentration; liquidity", "missing-evidence"]
    assert output["required_human_approval"] is True
    assert output["llm_backed"] is True
    assert output["llm_provider"] == "deepseek"
    assert output["llm_model"] == "deepseek-reasoner"
    assert output["llm_fallback_reason"] is None
    assert output["llm_floor_applied"] is False


def test_brain_orchestrator_floor_keeps_non_proceed_recommendation(monkeypatch):
    def mock_chat(self, request):
        return valid_brain_review_response(
            recommendation="proceed",
            rationale="LLM thinks the context is sufficient but highlights execution risk.",
            confidence="low",
            risks=["execution-risk"],
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    output = run_brain_orchestrator(risk_level="high")

    assert output["recommendation"] == "human_review_required"
    assert output["rationale"] == "LLM thinks the context is sufficient but highlights execution risk."
    assert output["confidence"] == "low"
    assert output["risks"] == ["execution-risk"]
    assert output["llm_backed"] is True
    assert output["llm_floor_applied"] is True


def test_brain_orchestrator_malformed_json_falls_back(monkeypatch):
    def mock_chat(self, request):
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-chat",
            content="not json",
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    output = run_brain_orchestrator()

    assert output["recommendation"] == "proceed"
    assert output["rationale"] == "No deterministic blocker found in this scaffold."
    assert output["llm_backed"] is False
    assert output["llm_fallback_reason"] == "invalid_json"
    assert output["llm_floor_applied"] is False


def test_brain_orchestrator_schema_invalid_falls_back(monkeypatch):
    def mock_chat(self, request):
        return valid_brain_review_response(recommendation="approve_and_execute")

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    output = run_brain_orchestrator()

    assert output["recommendation"] == "proceed"
    assert output["llm_backed"] is False
    assert output["llm_fallback_reason"] == "schema_invalid"


def test_brain_orchestrator_provider_error_falls_back(monkeypatch):
    def mock_chat(self, request):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    output = run_brain_orchestrator()

    assert output["recommendation"] == "proceed"
    assert output["llm_backed"] is False
    assert output["llm_fallback_reason"] == "provider_error"


def test_brain_orchestrator_timeout_falls_back_with_timeout_reason(monkeypatch):
    def mock_chat(self, request):
        raise TimeoutError("request timed out")

    monkeypatch.setattr(
        "phistyle_platform.runtime.runtime.DeepSeekProvider.chat",
        mock_chat,
    )

    output = run_brain_orchestrator()

    assert output["recommendation"] == "proceed"
    assert output["llm_backed"] is False
    assert output["llm_fallback_reason"] == "timeout"


def test_brain_orchestrator_dry_run_falls_back_with_no_api_key():
    output = run_brain_orchestrator()

    assert output["recommendation"] == "proceed"
    assert output["llm_backed"] is False
    assert output["llm_fallback_reason"] == "no_api_key"
    assert output["llm_floor_applied"] is False
