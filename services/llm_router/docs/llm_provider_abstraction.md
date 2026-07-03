# LLM Provider Abstraction

This document intentionally lives under `services/llm_router/docs/` because this phase is restricted to `services/llm_router/**`. It supersedes any root-level draft for this phase.

## Internal Schema

The router uses provider-neutral Python types:

- `UnifiedRequest`
- `UnifiedMessage`
- `ContentBlock`
- `UnifiedResponse`
- `UnifiedStreamEvent`
- `UnifiedUsage`

Provider wire formats must be normalized into these types before business logic sees them.

## Adapter Interface

Each provider adapter implements:

- `normalize_request()`
- `call()`
- `normalize_response()`
- `normalize_stream_event()`

Provider-specific behavior belongs inside `services/llm_router/providers/`.

## Routing Semantics

Routing config lives in:

```text
services/llm_router/config/llm_routing.yaml
```

Rules are evaluated top-to-bottom. First match wins. A mandatory fallback rule appears at the end.

Business code asks for a role:

- `brain`
- `worker`
- `tools`

It must not ask for a provider or model directly.

## Retry Semantics

Retry config lives in:

```text
services/llm_router/config/llm_retry.yaml
```

Each provider declares:

- `max_retries`
- `base_delay_seconds`
- `max_delay_seconds`
- `backoff_multiplier`
- `retry_on_status`
- `never_retry_stop_reasons`

`refusal` must be in `never_retry_stop_reasons`.

## Refusal Handling

Provider refusals are represented as `ProviderRefusal`.

They are:

- distinct from generic exceptions;
- non-retryable;
- not silently retried.

## Fable Thinking

Fable adaptive thinking cannot be disabled.

Rules:

- thinking blocks must not be inserted into normal conversation history;
- thinking/reasoning output must be stored separately or discarded;
- normalized responses keep thinking separate from user-visible content.

## Usage Tracking

Usage records include:

- request_id
- timestamp
- provider
- model
- role
- agent_id
- input_tokens
- output_tokens
- reasoning_tokens
- estimated_cost

Costs are computed from:

```text
services/llm_router/config/llm_pricing.yaml
```

No pricing values belong in Python code.

## Onboarding A Provider

1. Add provider config to `services/llm_router/config/llm_providers.yaml`.
2. Add retry config to `services/llm_router/config/llm_retry.yaml`.
3. Add pricing config to `services/llm_router/config/llm_pricing.yaml`.
4. Implement an adapter in `services/llm_router/providers/`.
5. Add normalization, stream, refusal, and routing tests.

