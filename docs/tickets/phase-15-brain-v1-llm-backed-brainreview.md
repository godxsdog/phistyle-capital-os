# Ticket: Phase 15 — Brain v1: LLM-Backed BrainReview (advisory)

FABLE-APPROVED: yes (2026-07-05)

FINAL VERDICT: ACCEPTED (Fable, 2026-07-06; commits 3bef0ca + 08e3a12
+ 958780a migration-id fix). STATUS: VERIFIED (2026-07-06): deployed to
Mac mini, migration 0007_brain_review_llm_meta applied cleanly (first
attempt failed on >32-char revision id, rolled back transactionally,
renamed, reapplied), live decision #3 (台指期 swing question) returned
llm_backed=true, provider=deepseek, model=deepseek-chat,
fallback=null, floor_applied=false. Fable review-miss recorded: the
revision-id length was reviewable in round 1 and missed; rule added to
implementation-ticket-standard §9.
- Round 1: Sonnet review found 1 BLOCKER (comma-in-LLM-risks → live
  500) + 1 LOW → FIX_REQUIRED. Round 2 fix verified by Fable directly
  (3-file diff, proportionate): sanitize commas→semicolons post-
  validation; regression + timeout tests added. 223 passed; 9 failures
  are pre-existing router/provider issues (diagnosis folded into the
  Phase 16 ticket).
- Governance calibration (Phase 15): extra Fable interventions 0;
  STOPs 0 (false 0); ticket length proportionate; Codex questions
  unanswered by ticket 0. Lesson recorded: the BLOCKER was a ticket
  gap (free-text LLM output meeting a comma-joined storage format) —
  future tickets must state storage-format constraints on any
  LLM-generated field.

VERDICT ROUND 1 (2026-07-06, on commit 3bef0ca): FIX_REQUIRED.
Everything passed review (floor rule, fallback taxonomy, idempotency,
override path, forbidden files, migration 0007 approved) EXCEPT:

FIX 1 [BLOCKER]: LLM risks containing commas crash the pipeline.
_serialize_risks (brain_review_service.py) raises ValueError on any
comma; LLM free text routinely contains commas; nothing catches it →
live 500 on POST /capital/decisions/{id}/run. REQUIRED FIX (exactly
this, do not choose another): in BrainOrchestrator, AFTER
_is_valid_llm_review passes, sanitize each risk string by replacing
"," with ";" before putting risks into the output. Do NOT reject
comma-containing reviews (that would discard good reviews); do NOT
change _serialize_risks or storage format. Add regression tests at
agent level AND full-pipeline level using an LLM risk string
containing commas, asserting success and sanitized storage.

FIX 2 [LOW]: add a test asserting llm_fallback_reason == "timeout"
when DeepSeekProvider.chat raises TimeoutError.

Scope of the fix round: phistyle_platform/runtime/runtime.py + the
four test files only. No other file may change. No migration change.
Commit as: fix: sanitize llm risk strings + timeout test (phase 15 r2)
VALID AFTER: Phase 14 verdict commit lands on main.
IMPLEMENTATION OWNER: Codex. REVIEW: Sonnet. VERDICT: Fable.

## 1. WHY THIS PHASE EXISTS

BrainOrchestrator is a deterministic if/elif stub
(phistyle_platform/runtime/runtime.py:413-515, self-labeled
`deterministic_stub: True`). This phase makes BrainReview content
model-generated while keeping every safety property deterministic.
See docs/strategy/current-roadmap.md §Phase 15.

## 2. USER VALUE

Run Analysis returns a model-generated critique of the user's
question+context (assumption challenges, unstated risks, missing
considerations) instead of canned sentences. NOT evidence-grounded
until Phase 18 — no prices/news/filings are cited. The UI shows
whether the LLM actually ran or the system fell back.

## 3. STRATEGIC DECISION ALREADY MADE (do not reopen)

- Provider: DeepSeek via the existing DeepSeekProvider
  (services/llm_router/providers/deepseek.py), same call pattern as
  DailyBriefAgent (runtime.py:46-129). Role: deep reasoner.
- Triage stays deterministic. Untouched.
- FLOOR RULE (exact semantics): run the existing deterministic
  `_review` first. If its recommendation != "proceed", the
  deterministic recommendation IS the stored recommendation; the LLM
  may only enrich rationale/risks/confidence. Only when the
  deterministic recommendation == "proceed" may the LLM replace the
  recommendation, with any valid enum value.
- `required_human_approval` stays hardcoded True.
- On ANY LLM failure (network, timeout, non-JSON, schema-invalid,
  missing API key): fall back to the full current deterministic output.
  The pipeline must never fail or change state because of the LLM.
- LLM JSON output contract (strict):
  {"recommendation": one of proceed|request_more_context|reject|defer|
   human_review_required, "rationale": string, "confidence": one of
   low|medium|high, "risks": [strings, 1-8 items]}
  Anything else = parse failure = fallback.
- Metadata persisted per BrainReview: llm_backed (bool),
  llm_provider (str|null), llm_model (str|null),
  llm_fallback_reason (str|null, e.g. "no_api_key", "timeout",
  "invalid_json", "schema_invalid"), llm_floor_applied (bool —
  true ONLY when a successful LLM response's recommendation was
  discarded by the floor rule; llm_floor_applied is always False
  whenever llm_backed is False).
- Baseline prompt skeleton (Codex may refine wording, not the
  contract): system-style instruction stating: you are an advisory
  investment decision reviewer; given question/context/options/
  risk_level/triage output, return ONLY the JSON object per the
  contract; challenge the thesis, name unstated risks; do not
  recommend trades or execution; be conservative under uncertainty.

## 4. CURRENT VERIFIED CONTRACTS

- BrainOrchestrator deterministic logic: runtime.py:459-515 — must be
  preserved verbatim as floor + fallback.
- Pipeline creates BrainReview once, reuses on re-run:
  capital_decision_support_service.py:113-116; idempotency via
  _latest_brain_review. Unchanged.
- DecisionLog draft idempotency: brain_decision_link_service.py:52-63.
  Unchanged.
- Terminal-state guard (Phase 14): decision_request_service.py.
  Unchanged.
- DeepSeekProvider dry-run behavior when DEEPSEEK_API_KEY missing.

## 5. IN SCOPE

- BrainOrchestrator: add LLM call + floor rule + fallback per §3.
- shared/models/brain_review.py: add the §3 metadata columns
  (all nullable, additive).
- Migration 0007: additive nullable columns on brain_reviews only.
- capital_decision_support_service._run_and_persist_brain_review and
  brain_review_service.create_brain_review: pass through metadata.
  The new create_brain_review parameters are OPTIONAL keyword arguments
  with defaults: llm_backed=False, llm_provider=None, llm_model=None,
  llm_fallback_reason=None, llm_floor_applied=False. The existing
  /decisions/brain/override handler (backend/app/main.py:772-801) is
  NOT modified beyond automatically inheriting the response fields —
  it relies on the defaults, so human-override reviews are correctly
  recorded as llm_backed=False.
- backend brain-review responses: include the new metadata fields.
- frontend decision detail page: small indicator on the BrainReview
  stage — "LLM-backed" vs "deterministic fallback: <reason>". Display
  only; no logic.
- Tests per §13.
- Janitorial (bundled): add `.python-version` containing `3.12` at repo
  root + one README line stating Python >=3.10 (runtime image 3.12);
  run the 8 previously-failing LLM router/provider tests under the
  3.12 venv and report pass/fail in the completion report (fix nothing
  there unless the failure is caused by this phase's changes).

## 6. OUT OF SCOPE

Triage changes; evidence retrieval; Fable provider; other providers;
prompt-tuning UI; streaming; retry logic beyond a single attempt;
scheduler; any HumanReview/DecisionLog/DecisionRequest logic change;
llm_usage_log tables; fixing unrelated router test failures.

## 7. EXPECTED FILES / LAYERS TO CHANGE

phistyle_platform/runtime/runtime.py (BrainOrchestrator only);
shared/models/brain_review.py; migrations/versions/0007_*.py;
shared/services/brain_review_service.py;
shared/services/capital_decision_support_service.py (metadata
pass-through only); backend/app/main.py (response fields only);
frontend/app/capital/decisions/[decisionRequestId]/page.tsx (display
only); tests/test_agent_runtime.py, tests/test_brain_review_service.py,
tests/test_capital_decision_support_service.py,
tests/test_brain_review_api.py (additions only);
`.python-version`; README.md (one line).

## 8. FILES / LAYERS THAT MUST NOT CHANGE

shared/services/human_review_service.py;
shared/services/brain_decision_link_service.py;
shared/services/decision_request_service.py;
shared/models/decision_request.py; shared/models/human_review.py;
shared/models/knowledge.py; TriageAgent and its tests;
services/llm_router/* (consume DeepSeekProvider as-is);
scripts/*; existing migrations; existing tests (no modifications).

## 9. DATA / MIGRATION EXPECTATION

EXPECTED: exactly one migration (0007), additive nullable columns on
brain_reviews per §3. Anything else (new tables, non-nullable columns,
data backfill, enum changes) = STOP.

## 10. STATE-TRANSITION RULES

None may be touched. LLM output must never influence any status field
on any table. `requires_human_review` semantics unchanged.

## 11. IDEMPOTENCY REQUIREMENTS

Re-running the pipeline on a request that already has a BrainReview
must NOT create a new one or re-call the LLM (existing
_latest_brain_review reuse). All Phase 12/13/14 idempotency and
final-state tests must pass unmodified.

## 12. ERROR HANDLING

Per §3: single attempt, 60s timeout budget via provider defaults;
any failure → deterministic fallback with llm_fallback_reason set;
never raise out of the pipeline for LLM reasons; never log the API key.

## 13. ACCEPTANCE TESTS (must exist and pass; monkeypatch
DeepSeekProvider.chat — no live API calls in tests)

Service/agent level: valid JSON → stored review has LLM content,
llm_backed=true; malformed JSON → deterministic output,
llm_backed=false, reason="invalid_json"; schema-invalid (bad enum) →
fallback; deterministic non-proceed + LLM proceed → deterministic
recommendation kept, llm_floor_applied=true; deterministic proceed +
LLM human_review_required → LLM recommendation stored; provider raises
→ fallback; no API key (dry-run) → fallback with reason and
llm_floor_applied=False; human-override path (/decisions/brain/
override) still works unmodified and records llm_backed=False;
required_human_approval always True in every branch.
Pipeline level: existing idempotency/final-state tests green
unmodified; re-run does not re-call LLM (assert via monkeypatch call
counter).
API level: brain-review response includes new metadata fields.
Full suite: `pytest` green under Python 3.12 venv, except failures
proven pre-existing and unrelated (list them explicitly if any).

## 14. MANUAL VERIFICATION (user)

After deploy + migration 0007 on the Mac mini: create a new capital
decision in the browser with DEEPSEEK_API_KEY set on the backend; Run
Analysis; confirm rationale is non-canned, the BrainReview stage shows
"LLM-backed", and approving still works end to end. Then create one
decision with the key unset (or provider forced to fail) and confirm
the fallback indicator shows. Sandbox agent sessions cannot verify
live runtime.

## 15. STOP CONDITIONS (additional)

Schema needs beyond §9; any temptation to have the LLM output affect
status/state; DeepSeekProvider interface turns out to need changes
(report, do not modify services/llm_router); frontend work requiring
backend logic beyond exposing stored fields.

## 16. COMPLETION REPORT FORMAT

Exactly docs/strategy/implementation-ticket-standard.md §Completion
report, including the pasted migration file for Fable review before
the user runs it.
