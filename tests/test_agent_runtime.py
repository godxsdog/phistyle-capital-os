import pytest

from phistyle_platform.runtime.runtime import CodeReviewAgent, create_default_runtime
from phistyle_platform.runtime.types import UnknownAgentError
from services.llm_router.types import LLMResponse


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
