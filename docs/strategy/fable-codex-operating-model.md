# Fable ⇄ Codex Operating Model

Status: APPROVED (Fable G0 session, 2026-07-04)

Hierarchy: USER (veto, values, irreversible authorization) → FABLE
(decisions) → approved ticket → CODEX / cheaper models (execution) →
independent review → FABLE verdict.

## Decision authority

FABLE OWNS: product identity, strategy, roadmap, phase sequencing,
architecture judgment, invariant definition and changes, trade-off
resolution, model routing, ticket approval, acceptance criteria,
accept/fix/redesign/abandon verdicts, deciding when NOT to build.

CODEX OWNS: implementation of approved tickets, bounded repo
investigation, code + tests, build fixes, mechanical refactors inside
ticket scope, exact evidence reporting.

HAIKU / EXPLORE OWNS: mechanical search, file discovery, repetitive
evidence collection, module inventory.

SONNET OWNS: fresh-context review of tickets (clarity/ambiguity),
implementation review against ticket + invariants, governance
consistency checks.

OPUS OWNS: second opinion only when a high-impact disagreement or
safety/execution-boundary dispute remains after Sonnet review.

USER OWNS: final veto; values, preferences, risk tolerance, spending;
authorization of anything irreversible — explicitly including trades,
payments, data deletion, external communication, RUNNING ANY DATABASE
MIGRATION (the Mac mini PostgreSQL is the sole live instance; a bad
migration is irreversible in practice), and deploys to the Mac mini.

## Prohibitions

FABLE MUST NOT: routinely write product code, act as default debugger,
bulk-edit, or spend budget on repetitive scanning. Fable personally
inspects critical evidence for high-leverage decisions; breadth is
delegated.

CODEX MUST NOT: invent roadmap direction, create phases, change
architecture or invariants, add unplanned migrations, broaden scope,
convert advisory behavior into execution, auto-create HumanReviews,
or report completion as bare "Done".

## The loop (mandatory for every phase)

1. FABLE DECIDES (roadmap phase approved in current-roadmap.md).
2. FABLE WRITES OR APPROVES THE TICKET
   (per implementation-ticket-standard.md).
3. CODEX IMPLEMENTS on a branch, within ticket scope.
4. CODEX REPORTS EVIDENCE using the completion report format.
5. INDEPENDENT REVIEW (fresh-context Sonnet) challenges the result
   against ticket, invariants, and stop conditions.
6. FABLE ISSUES EXACTLY ONE VERDICT:
   ACCEPTED | FIX_REQUIRED | REDESIGN_REQUIRED | ABANDONED.

Only ACCEPTED advances the roadmap. Implementation success ≠ strategic
acceptance.

PUSH DISCIPLINE (added 2026-07-06 after the 0009 incident):
implementation commits are NOT pushed until the Fable verdict is
ACCEPTED. `git push` publishes only verdicted work. Migration
commands always pin the approved revision id, never `head`.

## When Fable review is mandatory

- Ticket approval for every phase (before Codex starts).
- Final verdict for every phase (after Sonnet review).
- Any STOP report (see strategic-stop-conditions.md).
- Any proposed invariant change, migration beyond ticket expectation,
  or new external data source / provider.
- Anything touching the execution boundary.

## When Codex may proceed WITHOUT a new Fable session

All of the following must hold:
1. The phase is listed as APPROVED in current-roadmap.md.
2. A ticket exists that conforms to implementation-ticket-standard.md
   and is marked FABLE-APPROVED (in the ticket file header).
3. `git status` is clean on main and the phase's dependencies are
   recorded as ACCEPTED (verdict noted in the ticket file or
   current-roadmap.md).
4. No STOP condition has fired.

If any check fails → STOP and escalate. Weaker models verify these four
checks mechanically; they never interpret strategy.

## Escalation rules

- Codex hits ambiguity settled nowhere in ticket/strategy files → STOP
  report → Fable.
- Sonnet review finds BLOCKER/HIGH → back to Codex if within ticket,
  to Fable if the ticket itself is wrong.
- Sonnet and Codex disagree and it matters → Opus second opinion →
  still unresolved → Fable.
- Anything requiring irreversible real-world action → USER, always.

## Runtime model routing (product, not process)

- Deterministic code: state machine, gates, idempotency — no model.
- DeepSeek: BrainReview v1+, materiality triage, brief generation,
  summaries.
- Fable/frontier in runtime: not now; reconsider at Brain v2+ for
  high-risk reviews only, as its own approved phase.
- Triage stays deterministic until evidence shows it misroutes.
