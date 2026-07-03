# Brain Architecture

Date: 2026-07-03

Status: documentation patch only. This does not implement Fable API calls,
modify Agent Runtime code, modify LLM Router code, or change routing/provider
config.

## Purpose

PhiStyle OS needs to distinguish Fable as a normal model provider from Fable as
the system Brain.

Provider mode is an execution detail. Brain mode is an orchestration role.

## Two Fable Modes

### Provider Mode

In provider mode, Fable is called by the LLM Router like any other provider. A
caller requests a role or task type, the router selects a provider/model, and the
provider adapter executes the request.

Provider mode is useful for bounded prompts and high-risk reasoning calls, but it
does not by itself make strategic decisions for the operating system.

### Brain Mode

In Brain mode, Fable acts as an orchestrator. It can plan, delegate, review, and
decide. The Brain decides what should happen, which agents should run, what
context is needed, and when a final strategic judgment is warranted.

Brain mode is not just another provider route. It sits above the Agent Runtime
and uses the runtime and router as execution layers.

## Target Architecture

```text
Events / User Requests
     |
     v
Triage / Gatekeeper
     |
     v
Brain Orchestrator  <---->  Knowledge / Memory
     |                       (read summaries, write Decision Log)
     v
Agent Runtime
     |
     v
LLM Router
     |
     v
DeepSeek / OpenAI / Gemini / Local Models
```

## Runtime Brain-Candidate Roles

This list describes LLMs the system may call at runtime.

| Runtime role | Intended use |
| --- | --- |
| Fable Brain | High-level reasoning, planning, arbitration, and final strategic judgment. |
| DeepSeek | Cheap summarization, classification, bulk processing, and triage. |
| Gemini | Code/execution review only, scoped per Phase 7B. Not yet a general-purpose brain-tier provider, and not yet added to `config/llm_providers.yaml`. |
| Local models | Private/local tasks. |

Out of scope for this roles list: Codex is the development-time tool used to
build this system through the MacBook to GitHub workflow. It is not a runtime
component, is not routed to by the LLM Router, and this patch does not propose
the system calling Codex to modify its own code.

Any future self-modifying agent capability would need its own dedicated phase and
risk review.

## Layer Responsibilities

### Brain Orchestrator

The Brain owns strategic judgment. It decides what matters, what to delegate,
what evidence is sufficient, and when a decision should be recorded.

### Agent Runtime

The Agent Runtime executes tasks. It registers agents, runs agents, records run
results, and should eventually enforce human-approval gates. It does not own
strategic judgment.

### LLM Router

The LLM Router is an execution layer. It maps roles or task classes to model
providers and adapter behavior. It does not decide strategy.

## Cost-Control Principle

DeepSeek or a local model should act as triage/gatekeeper for low-cost screening,
summarization, classification, and bulk processing.

Fable should be awakened only for high-value or high-risk tasks.

The Triage/Gatekeeper escalation decision should reuse the same conceptual
pattern as Phase 7B's `escalate_to_fable` recommendation. The exact relationship
between them, such as shared code versus parallel concepts, should be resolved in
Phase 9 when the Triage Agent is designed.

## Memory Principle

The Brain needs access to Knowledge / Memory.

By default, the Brain should read summaries instead of raw full context. Raw
context should be pulled only when the Brain or a reviewer needs evidence-level
detail.

Brain decisions must be recorded in a Decision Log.

The Decision Log is a future table or store separate from `llm_usage_log`:

- `llm_usage_log` records token/cost metadata.
- Decision Log records strategic decisions.

Whether these stores share a `request_id` for correlation, and the Decision Log
schema itself, should be defined in Phase 10 when the Brain Orchestrator is
implemented.

## Routing-Logic Overlap

This patch does not resolve whether Phase 6D's task-type routing rules in
`config/llm_routing.yaml` remain in use as-is, get subsumed by the
Triage/Brain decision flow, or coexist alongside it.

That relationship should be resolved in Phase 9 and Phase 10.

## Future Phase Placeholders

| Phase | Focus |
| --- | --- |
| Phase 8 | Knowledge / Memory Layer |
| Phase 9 | Triage Agent |
| Phase 10 | Brain Orchestrator |
| Phase 11 | Brain Review Loop |
| Phase 12 | Capital App Intelligence |

## Scope Notes

This patch does not require changes to Phase 6D, Phase 6E, or Phase 7B tickets.
Their scoping stands as previously defined.

No Fable API calls are implemented here.

