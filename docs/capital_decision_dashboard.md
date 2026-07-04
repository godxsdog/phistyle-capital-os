# Capital Decision Dashboard v0

Date: 2026-07-04

Status: Phase 13 frontend dashboard.

## Purpose

Capital Decision Dashboard v0 is the first browser UI for the Capital decision
workflow. It lets the user create Capital investment decision records, run the
existing advisory pipeline, and explicitly record a final HumanReview.

## Routes

- `/capital/decisions`
- `/capital/decisions/new`
- `/capital/decisions/{decision_request_id}`

## APIs Reused

- `POST /capital/decisions`
- `GET /capital/decisions`
- `GET /capital/decisions/{decision_request_id}`
- `POST /capital/decisions/{decision_request_id}/run`
- `POST /decisions/decision-logs/{decision_log_id}/human-review`

The backend remains the source of truth. After Run Analysis, Approve, or Reject,
the UI refetches the decision detail instead of fabricating business state.

## HumanReview

HumanReview remains explicit. The dashboard never approves or rejects on page
load, after creation, or after pipeline completion.

Each DecisionLog can have exactly one final HumanReview. This is enforced by a
database unique constraint and service-layer duplicate-review rejection. Plural
HumanReview read endpoint names do not imply multiple final reviews.

The dashboard treats the embedded `human_review` field from
`GET /capital/decisions/{decision_request_id}` as the Capital detail source of
truth.

## Comment Contract

The HumanReview POST request accepts optional `comment`.

The HumanReview POST response does not return `comment`, and the current Capital
detail summary does not expose `comment` in its embedded `human_review` object.

Current limitation: the dashboard may submit an optional comment, but it does
not display the comment after final review.

## Record-Only Safety

Approval is record-only. Rejection is record-only.

The dashboard does not:

- execute trades;
- place orders;
- hedge automatically;
- fetch live market data;
- fetch news;
- connect brokerage accounts;
- sync portfolio positions;
- trigger workflows or automations;
- send emails;
- make payments;
- deploy;
- modify permissions.

No execution layer exists.

## Pipeline Behavior

Run Analysis is explicit. It calls the existing Phase 12 pipeline only after the
user clicks the action.

Run Analysis is hidden once a DecisionLog is finalized or a HumanReview exists.
Finalized states are preserved and are not visually regressed back to pending
review.

The UI displays unknown enum values as raw strings so future backend values do
not crash the dashboard.

## Current Limitations

- No frontend test framework exists in the repository yet.
- HumanReview comments are submitted but not shown in the Capital detail view.
- The dashboard does not include live market data or real portfolio awareness.
- There is no authentication in this phase.
