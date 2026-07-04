# Capital Decision Support v0

Date: 2026-07-04

Status: Phase 12 scaffold. Advisory, record-only, no execution layer.

## Purpose

Capital Decision Support v0 is a thin vertical application layer over the
generic decision system.

It lets the Capital app create and run structured investment decision records:

```text
Capital Decision Input
  -> DecisionRequest
  -> TriageResult
  -> BrainReview
  -> Proposed DecisionLog
  -> STOP
  -> Existing explicit HumanReview
```

## Reused Contracts

This phase reuses existing system contracts:

- DecisionRequest creation and persistence.
- TriageAgent and triage services.
- BrainOrchestrator and BrainReview services.
- Phase 10B DecisionLog draft creation.
- Phase 11 HumanReview behavior.

It does not duplicate Triage rules or BrainReview rules.

## Scope Boundaries

This phase does not:

- call Fable, Gemini, or DeepSeek;
- fetch live market data;
- fetch news;
- read brokerage accounts;
- read or sync real portfolio positions;
- implement scoring models;
- generate real investment intelligence;
- trade;
- place orders;
- hedge automatically;
- trigger workflows or automations;
- send emails;
- make payments;
- deploy;
- modify permissions.

The pipeline creates advisory decision records only.

## Human Review

HumanReview remains explicit. The Capital pipeline never calls Phase 11
HumanReview automatically.

Approval remains record-only. No execution layer exists.

`requires_human_review` is computed from actual HumanReview existence:

- `true` when no HumanReview exists for the linked DecisionLog.
- `false` when a HumanReview exists.

It is not inferred only from BrainReview recommendation, DecisionLog status, or
DecisionRequest status.

## Idempotency

Rerunning the pipeline is idempotent for a given Capital DecisionRequest.

Existing records are reused instead of duplicated:

- latest TriageResult;
- latest BrainReview;
- linked DecisionLog draft.

Latest means highest `created_at`, tie-broken by highest `id`.

Stale or broken historical links are not silently repaired. If
`BrainReview.proposed_decision_log_id` points to a missing DecisionLog, the
pipeline relies on Phase 10B stale-link behavior and returns an error.

## Finalized State Preservation

Finalized DecisionRequest states are never downgraded on repeated runs:

- `human_approved`;
- `rejected`;
- `archived`.

Finalized DecisionLog states are never downgraded. Existing approved or
rejected DecisionLogs keep their current status and `approved_by` value.

## Known Limitation

Concurrent calls to:

```text
POST /capital/decisions/{decision_request_id}/run
```

for the same `decision_request_id` may race because check-then-create is not
atomic in this phase.

This limitation is documented but not fixed in Phase 12.
