# Decision Request

Date: 2026-07-04

Status: Phase 8B scaffold. This is pre-Triage, pre-Brain-Orchestrator, and
pre-execution.

## Purpose

Decision Requests represent structured questions or issues before any
brain/orchestrator makes recommendations.

The future flow is:

```text
User / Event
  -> Decision Request
  -> Triage Agent
  -> Brain Orchestrator
  -> Decision Log
  -> Human Approval
  -> Future Action
```

Phase 8B only creates the data model, service functions, API endpoints, tests,
and documentation for Decision Requests.

## DecisionRequest vs DecisionLog

| Object | Meaning |
| --- | --- |
| DecisionRequest | A question or issue before judgment. |
| DecisionLog | A final or recorded decision after review. |

DecisionRequest captures the question, context, free-form options, risk level,
status, and optional links to Knowledge / Memory records.

DecisionLog records a decision made elsewhere. DecisionLog behavior from Phase
8A is unchanged by this phase.

## Why This Exists Now

Triage Agent and Brain Orchestrator need a structured object to work on. Without
Decision Requests, the system would jump directly from user/event text into
unstructured model calls.

This scaffold gives future phases a stable record to triage, review, and link to
Brain decisions.

## Human Approval Principle

`human_approved` is only a record status. It must not execute trades,
deployments, payments, emails, automations, permission changes, or any other
side effect.

All phases remain read-only and advisory until an explicit future execution
layer exists.

## Known Gap: No Status State Machine

Phase 8B does not enforce status transition rules. For example, `draft` can be
patched directly to `human_approved`.

Any valid enum value may currently be set via `PATCH` regardless of the current
status. This is documented as a known gap, not a silent bug. State-machine
enforcement is future scope for Phase 9 or Phase 10.

## Initial Schema Note

This DecisionRequest schema is the initial version. Phase 9 Triage Agent and
Phase 10 Brain Orchestrator may extend it with a real status state machine,
structured options, richer review metadata, and more explicit relationships to
Decision Log.

`options` is a free-form text field in this phase, not JSON.

## created_by Note

`created_by` is free text in this phase because no auth/user system exists yet.
It must not be used for authorization or permission decisions now or in future
phases until a real identity system is introduced.

## App Ownership

`app_id` must match an existing App Registry identifier. This phase validates
against the existing importable App Registry instead of duplicating an app list.

The current registry does not expose a `platform` app id. Adding platform-level
app ownership is a follow-up for the App Registry rather than something this
phase duplicates locally.

## API

```text
GET /decisions/requests
POST /decisions/requests
GET /decisions/requests/{id}
PATCH /decisions/requests/{id}/status
```

Create request:

```json
{
  "app_id": "capital",
  "decision_type": "investment",
  "question": "Should I reduce AVGO exposure?",
  "context": "AVGO is now concentrated in the portfolio.",
  "options": "hold | reduce 20% | hedge",
  "risk_level": "high",
  "status": "submitted",
  "created_by": "Kaichang",
  "related_knowledge_document_id": null,
  "related_decision_log_id": null
}
```

Status update:

```json
{
  "status": "triaged"
}
```

## Non-Goals

- No Fable calls.
- No Gemini calls.
- No DeepSeek calls.
- No Triage Agent.
- No Brain Orchestrator.
- No automatic execution.
- No trading.
- No automatic approvals.
- No status transition enforcement.
- No Capital intelligence.
- No legacy app integration.

