# Phase 6E Roadmap and Architecture Patch

Date: 2026-07-03

Status: documentation patch only.

## Purpose

Phase 6E closes roadmap gaps before continuing DeepSeek/Fable provider work. It
does not implement APIs, migrations, agent approval gates, trading logic, or
legacy app integration.

## Router Lineage Clarification

- Phase 2 LLM Router was Router v0 / prototype only.
- Phase 6D is allowed to replace Phase 2 router internals.
- Phase 2 router is not considered legacy.
- After this patch, resume Phase 6D as previously scoped.

The intended continuity is:

```text
Phase 2 Router v0 -> Phase 6D hardened provider abstraction -> provider work resumes
```

## Persistent LLM Usage Tracking Plan

The future table is `llm_usage_log`.

| Field |
| --- |
| `request_id` |
| `timestamp` |
| `provider` |
| `model` |
| `role` |
| `agent_id` |
| `input_tokens` |
| `output_tokens` |
| `reasoning_tokens` |
| `estimated_cost` |

This is design documentation only. Do not create Alembic or SQL migration files
in Phase 6E.

The design must stay aligned with Phase 6D `UnifiedUsage` and `UsageRecord`.
Pricing must come from `config/llm_pricing.yaml` and must never be hardcoded.

## App and Agent Mapping

This mapping is documentation only. No code reads it yet.

| App | Planned agents |
| --- | --- |
| Capital | Daily Brief Agent, News Agent, Scoring Agent, Portfolio Agent |
| Points Wallet | Points Agent |
| Dental PPT | Dental Case Agent, Evidence Agent |
| Travel | Travel Agent |
| Snowboard | Snowboard Agent |
| Shared | Echo Agent |

Points Wallet and Dental PPT remain legacy references only.

## Secrets Management

- `.env` lives on the Mac mini only.
- Docker Compose should use `env_file` when real provider secrets are needed.
- Never commit API keys.
- `.env.example` contains placeholders only.
- API keys must not appear in logs, test output, docs, error messages, or
  serialized objects.

## Human Approval Principle

No agent may execute real trades without explicit human confirmation.

Future enforcement belongs in the Agent Runtime, not individual agents. Phase 6E
does not add approval flags, runtime gates, broker integration, or trading
execution. Early phases remain read-only and dry-run only.

## Phase 6F Placeholder

Phase 6F should add CI before automatic deploy:

- CI on push.
- Run `pytest`.
- Run lint checks.
- Do not deploy if tests fail.

