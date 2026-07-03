# Human Approval Principle

Date: 2026-07-03

Status: architecture rule. No trading execution, approval flags, or runtime gates
are implemented in this phase.

## Rule

No agent may execute real trades without explicit human confirmation.

This applies to every app and every future provider path, including local models,
cloud models, batch agents, scheduled agents, and manually triggered agents.

## Enforcement Location

Enforcement should live in the Agent Runtime, not inside individual agents.
This is a future implementation requirement only; do not add approval code to
the Agent Runtime during Phase 6E.

Individual agents may propose actions, produce summaries, draft orders, or flag
risks. The runtime must be responsible for requiring confirmation before any
real-world irreversible action is executed.

## Early Phase Behavior

Early phases are read-only and dry-run only:

- No real trades.
- No order placement.
- No broker integration.
- No automatic execution based on model output.
- No background job may bypass human approval.

Future execution tools should include audit records showing who approved, when
they approved, what action was approved, and which agent proposed it.
