# Triage Agent

Date: 2026-07-04

Status: Phase 9A scaffold. Deterministic, advisory-only, and pre-Fable.

## Purpose

Triage Agent routes Decision Requests toward local handling, worker-model
preparation, or future Brain Orchestrator review.

The target flow is:

```text
Decision Request
  -> Triage Agent
  -> Triage Result
  -> Future Brain Orchestrator
  -> Decision Log
```

This phase only creates a deterministic triage scaffold. It does not call Fable,
Gemini, DeepSeek, or any other LLM.

## Objects

| Object | Meaning |
| --- | --- |
| DecisionRequest | The question or issue before judgment. |
| TriageResult | Advisory routing recommendation for a DecisionRequest. |
| DecisionLog | Final or recorded decision after review. |

TriageResult is not a final decision. It does not approve, reject, execute, or
archive anything.

## Not The Brain

Triage Agent is not the Brain. It does not make final strategic judgments and
does not decide final actions.

It only classifies routing recommendation with deterministic rules. Escalation
to Fable is advisory-only in this phase.

## Risk Level

Triage Agent does not independently assess risk level.

The output `risk_level` is an unmodified passthrough of the input `risk_level`
recorded on the DecisionRequest. Independent risk reassessment is future scope
and likely requires a real LLM call or dedicated review process.

## Rule Order

Rules are evaluated top to bottom. First match wins.

1. If `question` or `context` is empty or whitespace-only:
   `recommendation = reject_request`.
2. If `risk_level` is `high`:
   `recommendation = escalate_to_brain`.
3. If `decision_type` is `investment` or `medical`:
   `recommendation = escalate_to_brain`, unless risk is `low` and context
   contains the literal phrase `informational only`, case-insensitive.
4. If `decision_type` is `engineering` and question or context contains
   `security`, `secret`, `deployment`, `database migration`, `trading`, or
   `payment`:
   `recommendation = escalate_to_brain`.
5. Else if `risk_level` is `medium`:
   `recommendation = use_worker_model`.
6. Else:
   `recommendation = handle_locally`.

## Manual Overrides

`POST /decisions/triage/override` bypasses deterministic rules entirely. It
exists for human correction only, not as the default flow.

`created_by = "triage-agent"` is reserved for system-run triage results and is
rejected on manual overrides.

## Advisory Boundary

No workflow, trade, deployment, payment, email, permission change, or other
automation may be triggered by a TriageResult.

`recommendation = escalate_to_brain` does not call Fable in this phase.

`recommendation = reject_request` does not automatically change the
DecisionRequest status. Whether or how a human or future phase updates
DecisionRequest.status in response is out of scope here.

## Relationship To Phase 7B

Phase 7B introduced `escalate_to_fable` for code-review-specific advisory
recommendations.

Phase 9A introduces an analogous but separate `escalate_to_brain` mechanism for
DecisionRequests. They are not unified in this phase. A shared escalation
abstraction, if any, remains future scope.

## Non-Goals

- No Fable calls.
- No Gemini calls.
- No DeepSeek calls.
- No Brain Orchestrator.
- No investment logic.
- No automatic execution.
- No trading.
- No automatic approval.
- No workflow triggered from triage results.
- No legacy app integration.

