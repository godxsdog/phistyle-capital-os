# Implementation Ticket Standard

Status: APPROVED (Fable G0 session, 2026-07-04)
Applies to: every Codex (or other implementer) ticket from Phase 14 on.

Tickets live in `docs/tickets/phase-<N>-<slug>.md`. A ticket is valid
only with header `FABLE-APPROVED: yes (date)`.

## Mandatory sections (all 16, in order)

1. WHY THIS PHASE EXISTS — one paragraph linking to
   current-roadmap.md phase entry.
2. USER VALUE — what the user can do/trust afterward that they can't now.
3. STRATEGIC DECISION ALREADY MADE — settled questions Codex must not
   reopen (e.g. "provider is DeepSeek", "endpoint is guarded, not
   deleted").
4. CURRENT VERIFIED CONTRACTS — relevant existing behavior with file:line
   references (state machine, idempotency, guards).
5. IN SCOPE — exhaustive.
6. OUT OF SCOPE — explicit, including tempting adjacent work.
7. EXPECTED FILES / LAYERS TO CHANGE.
8. FILES / LAYERS THAT MUST NOT CHANGE.
9. DATA / MIGRATION EXPECTATION — exactly one of: NONE (migration = STOP)
   | EXPECTED: <described additive change> (anything else = STOP).
10. STATE-TRANSITION RULES — which transitions may be touched; default:
    none.
11. IDEMPOTENCY REQUIREMENTS — what must remain safe to re-run.
12. ERROR HANDLING — failure modes and required behavior (esp. LLM
    failure → deterministic fallback, never a crash or a state change).
13. ACCEPTANCE TESTS — named test cases that must exist and pass;
    `pytest` green is a floor, not the bar.
14. MANUAL VERIFICATION — exact human steps (browser/curl) with expected
    observations. Note: sandbox sessions cannot verify live runtime;
    manual verification on the Mac mini is the user's step.
15. STOP CONDITIONS — phase-specific, in addition to
    strategic-stop-conditions.md.
16. COMPLETION REPORT FORMAT — must be the format below.

## Completion report (mandatory, verbatim structure)

```
IMPLEMENTATION STATUS: NOT_STARTED | PARTIAL | IMPLEMENTED | VERIFIED | BLOCKED
TEST STATUS: <command run, counts passed/failed/skipped>
COMMIT STATUS: <yes/no, hashes>
PUSH STATUS: <yes/no>
DEPLOYMENT STATUS: <yes/no/not applicable>
RUNTIME STATUS: <verified live / not verified / not applicable>
MANUAL VERIFICATION REQUIRED: <exact steps remaining for the user>
CHANGED FILES: <full list>
BACKEND CHANGED: yes/no
MIGRATION CREATED: yes/no — if yes, paste the full migration file into
  the report; Fable verifies it is purely additive BEFORE the user is
  asked to run it on the Mac mini's sole PostgreSQL instance
DEPLOYMENT SCRIPTS CHANGED: yes/no
KNOWN LIMITATIONS: <list or "none">
```

Bare "Done"/"Complete"/"Finished" is not a completion report and is
rejected automatically.

## Proportionality

Sections may be answered in a single sentence where genuinely trivial
(e.g. "OUT OF SCOPE: everything except the guard clause"). Brevity is
not a defect; padding to satisfy section count is. Rigor scales with
risk, not with word count.

## Rules

- The ticket must remove strategic ambiguity before Codex starts. If
  Codex must choose between product behaviors, the ticket has failed —
  STOP and return it.
- Codex solves implementation problems (data structures, function
  boundaries, test design) freely within scope.
- Every invariant in CLAUDE.md applies to every ticket implicitly.
- Sonnet reviews every ticket for ambiguity before Codex starts, and
  every implementation against the ticket before the Fable verdict.
