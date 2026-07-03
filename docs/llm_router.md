# LLM Router

Date: 2026-07-03

Status: architecture scaffold only. This does not call real APIs, load API keys, or implement investment logic.

## Why This Exists

PhiStyle OS will need multiple AI workers over time:

- Fable 5 as the brain and orchestrator.
- Codex as the implementation worker.
- Local DeepSeek as a cheap reasoning and summarization worker.
- Future OpenAI, Claude, Ollama, or other local models.

The LLM Router exists so apps and agents do not hard-code model names or provider APIs. They should ask for a task type or model role, and the router should choose the provider according to policy.

## Model Roles

| Role | Intended use |
| --- | --- |
| `orchestrator` | Cross-module planning, high-risk decisions, final review, architecture direction. |
| `deep_reasoner` | Complex reasoning, multi-step analysis, lower-cost exploration before escalation. |
| `coder` | Implementation, local code changes, tests, diffs, refactors, bug fixes. |
| `fast_worker` | Small edits, formatting, comments, low-risk batch work. |
| `summarizer` | Summaries, compression, document cleanups, status reports. |
| `reviewer` | Code review, risk review, policy checks, final validation. |

## Routing Policy

| Task class | Preferred route |
| --- | --- |
| `high_risk_architecture` | Fable 5 |
| `complex_reasoning` | DeepSeek or Opus-class model |
| `code_implementation` | Codex |
| `docs_formatting_summaries` | Mini model |
| `local_private_data` | Local model only |

The current scaffold returns routing decisions only. It does not execute prompts.

## Keeping Fable Usage Low

Fable 5 should be reserved for decisions where better reasoning materially changes risk:

- cross-module architecture;
- database design;
- security;
- investment logic;
- scoring logic;
- high-risk final review.

Routine implementation, docs, formatting, low-risk summaries, and boilerplate should route to Codex, Mini, or local workers.

## Local DeepSeek Later

Local DeepSeek can fit as:

- a cheap summarizer for private notes;
- a first-pass reasoner before escalation;
- a local-only route for sensitive data;
- a fallback when cloud APIs should not receive private context.

The router keeps this future path explicit through the `local_private_data` policy and local provider entries.

## Adding New Providers

1. Add provider metadata to `services/llm_router/provider_registry.py`.
2. Map supported roles in `services/llm_router/policies.py`.
3. Keep provider credentials in environment variables, never in code.
4. Add tests that confirm routing decisions without making network calls.
5. Only later add execution adapters behind the router boundary.

## Non-Goals

- No real API calls.
- No API keys.
- No prompt execution.
- No investment logic.
- No legacy app integration.

