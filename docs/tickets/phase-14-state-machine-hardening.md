# Ticket: Phase 14 — State-Machine Hardening

FABLE-APPROVED: yes (2026-07-04)
VERDICT: ACCEPTED (Fable, 2026-07-05). STATUS: VERIFIED.
- Implementation: commit f2cf216. Sonnet independent review: 0 BLOCKER,
  0 HIGH. Target tests: 37 passed (Python 3.12 venv, matching the
  python:3.12-slim runtime image).
- Live verification (user, Mac mini runtime): PATCH human_approved→draft
  on decision 1 returned the 409 guard message; state unchanged.
- Governance calibration: Fable extra interventions 0; STOPs 0 (false
  STOPs 0); ticket length proportionate; unanswered-by-ticket Codex
  questions 0. No governance pruning needed.
- KNOWN LIMITATIONS carried forward: repo declares no Python version
  requirement (3.9 breaks on `Mapped[str | None]`; runtime is 3.12) —
  fold a `.python-version` + README line into the Phase 15 ticket;
  8 LLM router/provider test failures in Codex's 3.9 session are
  suspected environment issues — re-check under 3.12 during Phase 15.
VALID AFTER: the governance adoption commit (CLAUDE.md + docs/strategy/*
+ this ticket) lands on main. Codex must verify per
docs/strategy/fable-codex-operating-model.md §"proceed without Fable".
IMPLEMENTATION OWNER: Codex. REVIEW: Sonnet. VERDICT: Fable.

## 1. WHY THIS PHASE EXISTS

CLAUDE.md invariant 3 ("DecisionRequest and DecisionLog final states
never downgrade") is enforced on the pipeline path and the HumanReview
path, but NOT on the generic status PATCH path. See
docs/strategy/current-roadmap.md §Phase 14.

## 2. USER VALUE

A finalized (approved/rejected/archived) decision can never be silently
reverted by any API call. Trust in the decision record becomes total.

## 3. STRATEGIC DECISION ALREADY MADE (do not reopen)

- The PATCH endpoint is GUARDED, not deleted.
- Minimal guard clause, NOT a general transition-table framework.
- Terminal states: human_approved, rejected, archived.
- Sole allowed outgoing transitions from terminal states:
  human_approved → archived, rejected → archived.
- Same-status PATCH (no-op) is allowed and returns 200 unchanged.
- Violations return HTTP 409.

## 4. CURRENT VERIFIED CONTRACTS

- Unguarded writer: shared/services/decision_request_service.py:56-68
  (update_decision_request_status), exposed at
  backend/app/main.py:615-628 (PATCH /decisions/requests/{id}/status).
- Guarded paths that must stay untouched:
  capital_decision_support_service.py:245-256 (_progress_status,
  compare-and-set) and human_review_service.py:66-71 + 92-100
  (PROPOSED-only review, unique HumanReview, terminal transitions).
- Existing tests assert final-state preservation on pipeline re-run:
  tests/test_capital_decision_support_service.py:190-248.

## 5. IN SCOPE

- A terminal-state guard inside update_decision_request_status: if
  current status is terminal and requested status is not an allowed
  transition (§3), raise a new dedicated exception
  (e.g. DecisionRequestStatusTransitionError) in
  shared/services/decision_request_service.py.
- Map that exception to HTTP 409 with a clear detail message in
  backend/app/main.py.
- Tests (see §13).

## 6. OUT OF SCOPE

Everything else. Explicitly: no new states; no transition rules between
non-terminal states; no changes to DecisionLog or HumanReview logic; no
frontend changes; no transition-table abstraction; no refactors of
neighboring code.

## 7. EXPECTED FILES / LAYERS TO CHANGE

shared/services/decision_request_service.py; backend/app/main.py
(exception→409 mapping only); tests/test_decision_request_service.py;
tests/test_decision_request_api.py.

## 8. FILES / LAYERS THAT MUST NOT CHANGE

shared/models/*, migrations/*, frontend/*, phistyle_platform/*,
services/llm_router/*, scripts/*, shared/services/human_review_service.py,
shared/services/capital_decision_support_service.py,
shared/services/brain_decision_link_service.py.

## 9. DATA / MIGRATION EXPECTATION

NONE. Any migration requirement is a STOP.

## 10. STATE-TRANSITION RULES

Only the terminal-state guard in §3 is added. Transitions between
non-terminal states remain unrestricted (unchanged current behavior).

## 11. IDEMPOTENCY REQUIREMENTS

Same-status PATCH is a safe no-op. Pipeline re-run behavior must remain
byte-identical (existing tests must pass unmodified).

## 12. ERROR HANDLING

Guard violation → DecisionRequestStatusTransitionError → HTTP 409,
detail names current status, requested status, and the rule. State must
be unchanged after a rejected attempt (no partial commit).

## 13. ACCEPTANCE TESTS (must exist and pass)

Service level: for each terminal state × each disallowed target →
raises, state unchanged; human_approved→archived and rejected→archived
succeed; archived→anything raises; same-status no-op returns unchanged;
non-terminal transitions still work.
API level: PATCH human_approved→draft returns 409 and GET shows state
unchanged; PATCH human_approved→archived returns 200.
Full suite: `pytest` green with zero modifications to existing tests.

## 14. MANUAL VERIFICATION (user, on Mac mini, after deploy)

Against a finalized decision: `curl -X PATCH .../decisions/requests/
{id}/status -d '{"status":"draft"}'` → expect 409; browser detail page
still shows approved state. Sandbox agent sessions cannot verify live
runtime — the completion report must say so.

## 15. STOP CONDITIONS (in addition to strategic-stop-conditions.md)

Any schema change; any need to touch files in §8; discovery of OTHER
unguarded status writers (report them in the completion report under
KNOWN LIMITATIONS — do not fix them in this ticket); existing tests
failing before your changes.

## 16. COMPLETION REPORT FORMAT

Exactly the format in
docs/strategy/implementation-ticket-standard.md §Completion report.
Bare "Done" is rejected.
