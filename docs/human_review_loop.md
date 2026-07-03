# Human Review / Approval Loop

Date: 2026-07-04

Status: Phase 11 scaffold. Record-only human review, no execution layer.

## Purpose

Phase 11 adds an explicit human review step for proposed DecisionLog records.

The decision-record loop is:

```text
DecisionRequest
  -> TriageResult
  -> BrainReview
  -> Proposed DecisionLog
  -> Explicit Human Review
  -> Approved or Rejected Decision Record
```

## HumanReview

HumanReview is an explicit human decision record and audit history entry.

In this phase:

- `reviewer` is required free text, not authentication.
- `reviewer` is trimmed before validation and persistence.
- `comment` is optional.
- `review_decision` must be exactly `approve` or `reject`.
- only `proposed` DecisionLogs may receive a final review.
- one DecisionLog may have at most one final HumanReview.

Uniqueness is enforced at both the service layer and database layer. The
database unique constraint is a concurrency and integrity backstop, not a
replacement for service validation.

## Record-Only Approval

Approval is record-only.

`DecisionLog.status = approved` does not execute anything.

`DecisionRequest.status = human_approved` does not execute anything.

This phase must not trigger:

- trades;
- payments;
- deployments;
- emails;
- workflows;
- automations;
- permission changes;
- external actions.

No Action or Execution Layer exists yet. Future execution must be a separate,
explicit phase with its own safety review.

## Status Updates

For `review_decision = approve`:

- create HumanReview;
- set `DecisionLog.status = approved`;
- set `DecisionLog.approved_by = reviewer`;
- set `DecisionRequest.status = human_approved`;
- set `DecisionRequest.related_decision_log_id = DecisionLog.id`.

For `review_decision = reject`:

- create HumanReview;
- set `DecisionLog.status = rejected`;
- set `DecisionLog.approved_by = null`;
- set `DecisionRequest.status = rejected`;
- set `DecisionRequest.related_decision_log_id = DecisionLog.id`.

## Related Request Lookup

`DecisionLog.related_request_id` is a string, not a strict foreign key.

The service must distinguish:

- malformed values that cannot be parsed as a valid DecisionRequest id;
- valid ids where the related DecisionRequest is missing.

Neither failure mode may create a partial HumanReview or update statuses.

## Atomicity

HumanReview creation and related status updates are atomic.

The service uses one database session and commits only after all required
changes are ready:

- create HumanReview;
- update DecisionLog;
- update DecisionRequest.

If any required operation fails, the transaction rolls back and leaves no
partial HumanReview or mismatched statuses.

## API

Create a final human review:

```text
POST /decisions/decision-logs/{id}/human-review
```

Read review records:

```text
GET /decisions/human-reviews
GET /decisions/decision-logs/{id}/human-reviews
```

## Non-Goals

- No Fable calls.
- No Gemini calls.
- No DeepSeek calls.
- No network calls.
- No trading.
- No deployment.
- No payment.
- No email.
- No workflow or automation execution.
- No legacy app integration.
