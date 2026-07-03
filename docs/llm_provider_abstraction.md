# LLM Provider Abstraction

Date: 2026-07-03

Status: architecture hardening only. No investment logic, legacy integration, or API key exposure has been added.

## Why This Exists

LLM providers do not all behave like OpenAI-compatible chat APIs. They may differ in:

- wire request format;
- message roles;
- system prompt handling;
- streaming event shape;
- retry behavior;
- reasoning or thinking output;
- usage accounting.

The LLM Router therefore uses an internal provider-neutral schema and provider adapters.

## Internal Schema

Core types live in `services/llm_router/types.py`:

- `Message`
- `NormalizedLLMRequest`
- `NormalizedLLMResponse`
- `NormalizedStreamEvent`
- `UsageRecord`

Business logic should not depend on provider wire formats.

## Provider Adapter Interface

Provider adapters implement:

- `normalize_request()`
- `call()`
- `normalize_response()`
- `normalize_stream_event()`

`chat()` remains a convenience wrapper, but provider-specific behavior should stay inside provider adapters.

## Config Files

Provider config:

```text
config/llm_providers.yaml
```

Routing config:

```text
config/llm_routing.yaml
```

Routing rules should be changed in config, not scattered through business logic.

## Retry Config

Each provider can declare:

- `max_attempts`
- `backoff_seconds`
- `retry_on_status`

This is architecture-only for now. Retry execution is not implemented yet.

## Usage Tracking

Usage records include:

- provider;
- model;
- role;
- agent_id;
- input_tokens;
- output_tokens;
- reasoning_tokens;
- estimated_cost.

Reasoning tokens are tracked separately from normal output tokens.

## Fable Thinking Notes

Fable adaptive thinking cannot be disabled.

Rules:

- thinking blocks must not be inserted into normal conversation history;
- thinking/reasoning output must be stored separately or discarded;
- normal assistant content and thinking content must remain separate;
- Fable remains restricted to high-risk orchestration routes.

## Non-Goals

- No investment logic.
- No legacy app changes.
- No API keys in code or logs.
- No provider-specific wire format in business logic.

