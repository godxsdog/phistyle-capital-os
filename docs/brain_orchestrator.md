# Brain Orchestrator

Date: 2026-07-04

Status: Phase 10A scaffold. Deterministic, advisory-only, and pre-Fable.

## Purpose

Brain Orchestrator takes a triaged DecisionRequest and produces a structured
BrainReview record.

Current target flow:

```text
Decision Request
  -> Triage Agent
  -> Triage Result
  -> Brain Orchestrator
  -> Brain Review
  -> Decision Log
  -> Human Approval
  -> Future Action
```

## Not Fable Yet

Brain Orchestrator is not the Fable API yet. This phase uses deterministic stub
review rules only.

Future Fable Brain may replace or augment the stub reasoning.

## Object Boundaries

| Object | Meaning |
| --- | --- |
| DecisionRequest | The question or issue before judgment. |
| TriageResult | Advisory routing recommendation for a DecisionRequest. |
| BrainReview | Advisory Brain-level review output. |
| DecisionLog | Final or recorded decision after review. |

BrainReview is advisory-only. It does not execute actions, approve decisions,
trade, deploy, pay, email, trigger workflows, or change permissions.

## Status Boundary

A BrainReview, regardless of recommendation, does not automatically change
DecisionRequest.status.

Any status transition in response to a BrainReview remains a separate future
human-or-later-phase-driven action.

## Human Approval

Human approval remains required before any future execution.

`required_human_approval` is always `true` across all six deterministic rules in
this phase. There is currently no code path that produces `false`. This is
intentional because all early-phase decisions require human approval per the
Brain-first principle. A future phase may introduce conditions under which this
can be false.

## Confidence Values

Confidence values in the deterministic rules are fixed placeholders. They are
not derived from any actual certainty measure until Fable is integrated.

They exist to keep the output schema stable for future phases, not to convey real
assessed confidence in Phase 10A.

## proposed_decision_log_id

`proposed_decision_log_id` is included now for forward compatibility but is not
populated by deterministic rules in this phase.

Only `/decisions/brain/override` can set it manually for testing and
documentation purposes. It will start being populated by system behavior in a
future phase such as Phase 11.

## Deterministic Rules

Rules are evaluated top to bottom. First match wins.

0. If `triage_result_id` is missing, the referenced TriageResult cannot be found,
   or `triage_recommendation` is null:
   `recommendation = human_review_required`, `confidence = high`.
1. Else if `triage_recommendation = reject_request`:
   `recommendation = reject`, `confidence = medium`.
2. Else if question or context is empty:
   `recommendation = request_more_context`, `confidence = high`.
3. Else if `triage_recommendation = escalate_to_brain`:
   `recommendation = human_review_required`, `confidence = medium`.
4. Else if `risk_level = high`:
   `recommendation = human_review_required`, `confidence = medium`.
5. Else if `triage_recommendation = use_worker_model`:
   `recommendation = defer`, `confidence = medium`.
6. Else:
   `recommendation = proceed`, `confidence = low`.

Rule 0 is a deliberate safety default. A request that skipped triage must never
fall through to `proceed`.

## Manual Overrides

`POST /decisions/brain/override` bypasses deterministic rules entirely. It exists
for human/manual correction only, not as the default flow.

`created_by = "brain-orchestrator"` is reserved for system-created reviews and
is rejected on the override endpoint.

## Non-Goals

- No real Fable calls.
- No Gemini calls.
- No DeepSeek calls.
- No investment logic.
- No action execution.
- No trading.
- No automatic approval.
- No workflow triggers.
- No automatic DecisionLog creation from BrainReview.
- No legacy app integration.

