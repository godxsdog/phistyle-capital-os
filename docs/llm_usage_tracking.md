# LLM Usage Tracking

Date: 2026-07-03

Status: architecture plan only. No persistence, SQL migration, or database table
is implemented in this phase.

## Purpose

PhiStyle OS needs a persistent usage log for every future LLM request so model
cost, provider selection, agent behavior, and retry/refusal patterns can be
audited.

The Agent Runtime and LLM Router should eventually write one record per completed
LLM request, including dry-run and refusal outcomes when they represent a real
routing decision.

This design must stay consistent with the Phase 6D `UsageRecord` and
`UnifiedUsage` schema. `UnifiedUsage` captures token counts returned by a
provider adapter. `UsageRecord` adds request metadata, routing metadata, and the
estimated cost.

## Planned Table

`llm_usage_log`

| Field | Purpose |
| --- | --- |
| `request_id` | Stable request identifier for tracing across runtime, router, and logs. |
| `timestamp` | Time the usage record was created. |
| `provider` | Provider selected by the router, such as DeepSeek, Fable, OpenAI, or local. |
| `model` | Provider model identifier selected by routing config. |
| `role` | Business-facing role requested by the caller. |
| `agent_id` | Agent that initiated the request, if applicable. |
| `input_tokens` | Tokens counted for input messages. |
| `output_tokens` | Tokens counted for normal output. |
| `reasoning_tokens` | Tokens counted for thinking or reasoning output, when provided. |
| `estimated_cost` | Estimated cost computed from pricing config. |

This table is future work. Do not create Alembic or SQL migration files for it
until a database implementation phase explicitly requests persistence.

## Pricing Rule

Pricing must be read from `config/llm_pricing.yaml` and must never be hardcoded
in business logic, provider adapters, tests, docs, or database models.

The cost calculation should treat missing pricing as an explicit configuration
gap, not as permission to invent defaults.

## Privacy Notes

The usage log stores metadata and token counts only. It must not store API keys,
raw prompts, `.env` values, private repository contents, financial account data,
or medical records.
