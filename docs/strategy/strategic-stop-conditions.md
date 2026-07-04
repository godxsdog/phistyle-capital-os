# Strategic STOP Conditions

Status: APPROVED (Fable G0 session, 2026-07-04)
Applies to: Codex, Haiku, Sonnet, and any future agent working in this
repository. STOP means: cease implementation, write the STOP report,
escalate. Do not "fix it while you're there".

## Universal STOP triggers

1. Roadmap direction unclear, or the task's phase is not APPROVED in
   docs/strategy/current-roadmap.md.
2. A critical invariant (CLAUDE.md list) would change or be weakened.
3. A migration appears that the ticket did not declare, or a declared
   migration stops being purely additive.
4. Implementation scope expands materially beyond IN SCOPE.
5. Frontend work turns out to require backend business-logic changes.
6. Repository reality differs materially from ticket assumptions
   (missing files, different contracts, failing baseline tests).
7. Existing tests contradict expected behavior.
8. Stale links or historical data inconsistency would need repair
   (invariant 7: never silently repair history).
9. Any change would introduce automatic execution or an external-action
   layer (trades, payments, email, messages, deploy hooks on approval).
10. Irreversible-action authorization is unclear.
11. The source of truth (repo, DB schema, strategy files) is
    unavailable or contradictory.
12. A strategic choice arises that the ticket does not settle.
13. Credentials/paid services are required that the user has not
    provided.

## Mandatory STOP report format

```
STOP REASON: <one line>
EVIDENCE: <what was observed>
FILES AND LINES: <exact references>
EXPECTED: <what the ticket/strategy assumed>
FOUND: <what is actually there>
SAFE OPTIONS: <2-3 options, each reversible>
RECOMMENDATION: <one option, with why>
DECISION NEEDED FROM: FABLE | USER
```

## After a STOP

- Leave the working tree in a clean, explained state (no half-applied
  changes without a note).
- Do not commit unless the ticket already authorized commits and the
  commit is self-consistent.
- Never push or deploy after a STOP.

## Session-start protocol (all future agents)

Before any work:
1. `git status` and current branch (expect clean main unless the ticket
   says otherwise; the one-time strategy-adoption commit of CLAUDE.md +
   docs/strategy/* is the expected exception at adoption time).
2. Read CLAUDE.md.
3. Read docs/strategy/current-roadmap.md — identify the current phase
   and its verdict state.
4. Locate the ticket (docs/tickets/) if the task is implementation;
   verify FABLE-APPROVED header.
5. Classify the task and route:
   - STRATEGIC (identity, roadmap, architecture, invariants) → Fable
     decision process; do not proceed on a weaker model.
   - IMPLEMENTATION → Codex, ticket required.
   - MECHANICAL SEARCH / inventory → Haiku / Explore.
   - INDEPENDENT REVIEW → Sonnet, fresh context.
   - UNRESOLVED HIGH-IMPACT DISPUTE → Opus, then Fable.
   - DEPLOYMENT DEBUGGING → follow docs/deployment.md; runtime actions
     on the Mac mini are executed by the user unless explicitly
     authorized.
6. If any check fails or the task doesn't fit a category → STOP report.
