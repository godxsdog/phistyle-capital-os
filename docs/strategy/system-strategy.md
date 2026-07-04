# PhiStyle Capital OS — System Strategy

Status: APPROVED (Fable G0 session, 2026-07-04)
Owner: Fable (strategy) / User (veto)
Supersedes: identity ambiguity in README.md and ROADMAP.md "Future Product Phases"

## 1. What PhiStyle actually is today (verified 2026-07-04)

A well-tested, human-in-the-loop **decision record-keeping workflow** for
investment decisions — with **no intelligence and no investment data yet**.

Verified reality (see git history through 844ccd8):

- The Capital vertical works end to end in the browser:
  DecisionRequest → Triage → BrainReview → DecisionLog draft → explicit
  HumanReview → final record. Final states are preserved on re-run.
- TriageAgent and BrainOrchestrator are **deterministic if/elif rules**
  (self-labeled `deterministic_stub: True`). No LLM is called anywhere in
  the capital pipeline.
- The only real LLM integration is DailyBriefAgent → DeepSeek (manual
  invocation only; no scheduler exists).
- Knowledge/Memory tables exist but are **dormant**: nothing in the live
  pipeline reads or writes KnowledgeDocument or AgentMemory.
- 8 of 10 registered LLM providers are stubs with no adapter code; only
  DeepSeek and Fable have adapters. Fable provider points at a
  placeholder URL. The AgentRuntime abstraction is bypassed by the capital
  pipeline (direct in-process instantiation — which is correct and simpler).
- No execution layer exists anywhere. Approval is record-only. This is
  correct and must stay so.

Honest summary: the system is currently a **decision diary with a
state machine**. The state machine is good. The diary has no brain.

## 2. Identity decision

PRIMARY IDENTITY
: **Personal investment decision-intelligence system.** Its job is to
  identify events that materially change investment decisions, ground
  decision reviews in real evidence, and keep an auditable record of every
  decision and its outcome. Capital is the product. Everything else is
  plumbing.

SECONDARY IDENTITIES (infrastructure, never roadmap drivers)
: The generic decision workflow engine (DecisionRequest/Triage/Brain/
  HumanReview) — keep it generic in schema, Capital-specific in behavior.
: The LLM router/provider layer — exactly as many providers as are used.

IDENTITIES TO AVOID
: A general-purpose AI agent platform. No new apps (points-wallet, dental,
  travel, snowboard stay FUTURE/frozen).
: A workflow-engine product. No scheduler framework, no multi-agent
  orchestration framework beyond what Capital needs.
: An autonomous trading system. Execution stays out (see §5).

WHY: One user, one working vertical, zero intelligence. Every hour spent on
platform generality is an hour not spent making the one vertical smart.
The last five phases (9A–13) built workflow scaffolding; the marginal value
of more scaffolding is now near zero, while the marginal value of the first
real model-driven, evidence-grounded review is the whole product.

## 3. What it should become (18-month direction)

1. Evidence in: watchlist-driven ingestion of prices, news, filings —
   stored in the (currently dormant) Knowledge layer.
2. Intelligence on: LLM-backed BrainReview that cites evidence, challenges
   the user's thesis, and states risks — advisory-only.
3. Signal out: a scheduled materiality brief that surfaces only events that
   change a decision, not news summaries.
4. Learning loop: decision outcome tracking so past decisions and results
   feed future reviews.

## 4. What it must not become

- No automatic trade/payment/external action from any approval — ever
  without a separate, explicitly user-authorized execution phase (§5).
- No multi-tenant / multi-user platform work.
- No provider zoo: providers are added only when a phase needs them.
- No RAG/vector/knowledge-graph infrastructure before the summary-first
  Knowledge layer is actually read by the Brain and shown to be limiting.
- No local model serving (Ollama/vLLM/SGLang/speculative) until a real
  private-data workload exists. Phase 2.5 is FROZEN.

## 5. Execution boundary (binding)

The system remains **advisory-only for at least the next 7 phases**
(through outcome tracking). Execution assistance may be *considered* only
when ALL of the following exist:

1. Evidence ingestion running reliably for 3+ months.
2. LLM-backed BrainReview in daily use with human agreement tracked.
3. Outcome tracking with a meaningful decision history (≥ 20 finalized
   decisions with recorded outcomes).
4. A written execution-phase design approved by Fable AND explicitly
   authorized by the user.

Never fully automatic, regardless of maturity: trade submission, payments,
transfers, external communication on the user's behalf, deletion of
decision history.

## 6. Strategic priorities (ordered)

1. Enforce the invariants the docs already claim (close the status-PATCH
   downgrade gap).
2. Make BrainReview model-driven (advisory, deterministic fallback).
3. Get real evidence into the system (watchlist, prices, headlines).
4. Scheduled materiality brief.
5. Evidence-grounded Brain + activate Knowledge layer reads.
6. Outcome tracking.

Everything not on this list is deferred or frozen. See
`current-roadmap.md` for phase definitions and
`fable-codex-operating-model.md` for who does what.

## 7. Architecture direction

- Keep: the state machine, idempotent pipeline, in-process service calls,
  DB-level constraints, backend-owns-state, thin frontend.
- Keep dormant (do not delete, do not extend): AgentRuntime/AgentRegistry
  generic surface, App Registry future apps, stub provider registry
  entries, scheduler placeholder.
- Delete when convenient (janitorial, bundle into any nearby phase):
  `/platform/` README-only dir. Nothing else is worth a deletion phase.
- Simplify rule: the capital pipeline calls agents directly in-process.
  Do NOT route it through AgentRuntime for architectural purity.
- Deterministic forever: state transitions, idempotency keys, approval
  gates, final-state preservation, migration application.
- Model-driven (phased): BrainReview content, materiality triage of
  ingested events, brief generation, evidence summarization.
- Fable-in-runtime: NOT NOW. The Fable provider URL is a placeholder.
  Runtime intelligence starts with DeepSeek (wired, cheap). A frontier
  model inside the runtime is reconsidered only at Brain v2+ for high-risk
  reviews, and requires a real provider integration phase.
