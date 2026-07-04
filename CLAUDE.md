# PhiStyle Capital OS — Agent Router

This file is an index. Strategy lives in docs/strategy/. Read this first,
then route yourself. Do not expand this file past 150 lines.

## What this system is

Personal investment decision-intelligence system. Advisory-only,
human-in-the-loop pipeline:
DecisionRequest → Triage → BrainReview → DecisionLog draft → explicit
HumanReview → final record. No execution layer exists; approval is
record-only. Capital is the only active vertical.

## Current verified state

- Phase 13 (Capital Decision Dashboard v0) complete; deployed to the
  Mac mini LAN runtime and browser-verified there by the user. This is
  a home-LAN runtime claim, not a public-production assertion.
  Latest strategy baseline: commit 844ccd8.
- Triage and BrainOrchestrator are deterministic stubs (until Phase 15).
- Knowledge/Memory tables exist but are dormant (until Phase 16).
- Next approved phase and full roadmap: docs/strategy/current-roadmap.md.

## Operating hierarchy

USER (veto, values, irreversible authorization)
→ FABLE (strategy, architecture, roadmap, tickets, verdicts)
→ CODEX (implementation of FABLE-APPROVED tickets only)
→ SONNET (fresh-context review) / HAIKU (mechanical search)
→ OPUS (second opinion on unresolved high-impact disputes only).

Fable decides; others execute. Codex never invents strategy, phases,
migrations, or scope. Details:
docs/strategy/fable-codex-operating-model.md.

## Critical invariants (binding; changes require Fable + user)

1. Human approval is explicit; HumanReview is never auto-created.
2. No automatic trade, payment, message, deploy, or external action —
   approval and rejection are record-only.
3. DecisionRequest and DecisionLog final states never downgrade.
4. Re-running the capital pipeline preserves finalized states.
5. DecisionLog draft creation from BrainReview is idempotent.
6. One DecisionLog has at most one final HumanReview.
7. Stale/broken historical links are never silently repaired.
8. Backend owns business state; frontend never computes transitions.
9. Internal pipeline stages use in-process calls, not HTTP loopback.
10. Active PostgreSQL data stays on Mac mini local storage (never NAS).
11. Unexpected schema/migration requirements are STOP conditions.
12. A frontend phase must not silently expand into backend logic.
13. "Done" alone is not a completion report — use the format in
    docs/strategy/implementation-ticket-standard.md.

Known gap being fixed in Phase 14: the generic status PATCH endpoint
does not yet enforce invariant 3. Do not build on that endpoint.

## Session start (mandatory)

1. `git status` + branch (expect clean main).
2. Read docs/strategy/current-roadmap.md for the current phase.
3. Implementation task → require a FABLE-APPROVED ticket in
   docs/tickets/. No ticket → STOP.
4. Route by task type per docs/strategy/strategic-stop-conditions.md
   §Session-start protocol.

## STOP triggers (summary)

Unclear direction; invariant change; unexpected migration; scope
expansion; frontend needing backend changes; repo differs from ticket
assumptions; tests contradict expectations; anything introducing
execution/external actions; unclear irreversible authorization.
Full list + mandatory STOP report format:
docs/strategy/strategic-stop-conditions.md.

## Strategy files

- docs/strategy/system-strategy.md — identity, direction, execution
  boundary, what not to build.
- docs/strategy/current-roadmap.md — approved Phases 14–20, frozen and
  abandoned work, reassessment triggers.
- docs/strategy/fable-codex-operating-model.md — authority, loop,
  escalation, model routing.
- docs/strategy/implementation-ticket-standard.md — mandatory ticket
  sections and completion report.
- docs/strategy/strategic-stop-conditions.md — STOP rules and
  session-start protocol.

## Deployment facts (do not rediscover)

Dev: MacBook, this repo. Runtime: Mac mini 192.168.0.216
(~/Server/phistyle-capital-os), frontend :3000, backend :8000, deploy via
./scripts/remote_deploy.sh. NAS 192.168.0.223 = cold storage only.
Migrations (only when a phase declares one):
`cd ~/Server/phistyle-capital-os && /usr/local/bin/docker-compose exec
backend python -m alembic -c /app/alembic.ini upgrade head`.
Sandbox agent sessions cannot verify live runtime — say so explicitly.
