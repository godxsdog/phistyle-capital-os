# BrainReview to DecisionLog Draft Link

Date: 2026-07-04

Status: Phase 10B scaffold. Explicit, idempotent, pre-Fable,
pre-human-approval-workflow, and pre-execution.

## Purpose

Phase 10B links advisory BrainReview records to durable DecisionLog records by
creating proposed DecisionLog drafts through an explicit endpoint.

This phase does not create approvals or execute anything.

## Object Boundary

| Object | Meaning |
| --- | --- |
| BrainReview | Advisory analysis from the Brain Orchestrator scaffold. |
| DecisionLog | Durable recorded decision. |

This phase creates proposed DecisionLog drafts only.

## Explicit Draft Creation

Draft creation is explicit. `POST /decisions/brain/run` must not create a
DecisionLog automatically.

The only draft-creation path in this phase is:

```text
POST /decisions/brain-reviews/{id}/decision-log-draft
```

`BrainReview.proposed_decision_log_id` is populated only by this explicit
draft-creation endpoint in Phase 10B.

## Generated Draft Rules

Generated drafts always use:

- `DecisionLog.status = proposed`
- `DecisionLog.approved_by = null`
- `DecisionLog.title = DecisionRequest.question`
- `DecisionLog.decision = BrainReview.recommendation`
- `DecisionLog.rationale = BrainReview.rationale`
- `DecisionLog.reviewed_by = BrainReview.created_by`
- `DecisionLog.related_request_id = str(DecisionRequest.id)`

`proposed_by` may be supplied as free text. If omitted, it defaults to
`BrainReview.created_by`.

This phase does not accept `approved_by` input.

## Idempotency

If a BrainReview already has `proposed_decision_log_id` and the linked
DecisionLog exists, the endpoint returns the existing DecisionLog and
`created = false`.

If `proposed_decision_log_id` points to a missing DecisionLog, the endpoint
returns an error. It must not silently create a replacement or overwrite the
stale reference.

## Safety Boundary

Creating a DecisionLog draft does not:

- approve anything;
- execute anything;
- trade;
- deploy;
- pay;
- email;
- trigger automation;
- modify permissions;
- trigger workflows;
- mutate DecisionRequest status.

`DecisionLog.status = approved` remains record-only in the current architecture
and must not trigger side effects.

Human approval workflow and execution layer are future scope.

## No Migration Expected

No Alembic migration is expected in Phase 10B.

`BrainReview.proposed_decision_log_id` already exists from Phase 10A. If a
future implementation discovers a missing schema element, stop and review the
schema gap before creating or modifying any migration.

## Non-Goals

- No Fable calls.
- No Gemini calls.
- No DeepSeek calls.
- No network calls.
- No real Brain reasoning.
- No investment logic.
- No approval workflow.
- No execution layer.
- No legacy app integration.

