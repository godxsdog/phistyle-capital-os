# Code Review Agent

Date: 2026-07-03

Status: scaffold only. Real Gemini calls are not implemented.

## Purpose

Code Review Agent reviews code changes and returns an advisory-only
recommendation. It does not modify code, approve changes, merge changes, deploy
changes, or replace human review.

Recommendation is advisory-only; no current or future automation may act on it
without a human-in-the-loop step, consistent with Phase 6E's human-approval
principle.

## Agent

| Field | Value |
| --- | --- |
| Agent id | `code-review-agent` |
| Name | Code Review Agent |
| Role | `reviewer` |

## Input Schema

```json
{
  "diff": "...",
  "scope": "backend | frontend | llm_router | docs",
  "risk_level": "low | medium | high"
}
```

## Output Schema

```json
{
  "summary": "...",
  "critical_issues": [],
  "medium_issues": [],
  "low_issues": [],
  "architecture_risks": [],
  "security_risks": [],
  "test_gaps": [],
  "recommendation": "approve | request_changes | escalate_to_fable"
}
```

## LLM Boundary

`call_llm()` is injectable and mockable. Until real Gemini support is wired in,
it returns a stub response.

These fields come only from `call_llm()`:

- `summary`
- `critical_issues`
- `medium_issues`
- `low_issues`
- `architecture_risks`
- `security_risks`

The agent itself does not perform semantic code analysis for those fields.

## Deterministic Rule Engine

The scaffold includes narrow deterministic checks:

- secret detection using explicit regex patterns;
- provider-specific logic outside `adapters/` or `providers/`, using path-based
  checks only;
- missing tests for behavior changes;
- invalid `scope` or `risk_level` validation.

Secret patterns:

- `sk-ant-`
- `sk-`
- `API_KEY=`
- `-----BEGIN PRIVATE KEY-----`

Provider names:

- `deepseek`
- `fable`
- `openai`
- `ollama`

Provider-specific logic is flagged only when a changed file is outside
`adapters/` and `providers/` and the diff text contains a known provider name.
No semantic analysis is performed.

## Rule Priority

1. If secrets are detected, `recommendation = request_changes`.
2. Else if provider-specific logic appears outside `adapters/` or `providers/`,
   `recommendation = request_changes`.
3. Else if `risk_level` is `high`, `recommendation = escalate_to_fable`.
4. Else if behavior changes have no accompanying tests, add `test_gaps` and
   `recommendation = request_changes`.
5. Else `recommendation = approve`.

Invalid or unrecognized `scope` or `risk_level` returns
`recommendation = request_changes` and adds a note to `critical_issues`.

## Non-Goals

- No real Gemini API calls.
- No legacy app changes.
- No investment logic.
- No auto-merge.
- No auto-approval.
- No future automation may act on the recommendation without human review.

