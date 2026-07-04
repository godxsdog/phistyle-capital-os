# Current Roadmap — Approved Phases 14–20

Status: APPROVED (Fable G0 session, 2026-07-04)
ADOPTION: the user commits CLAUDE.md + docs/strategy/* to main as a
single adoption commit before any phase work starts. Until that commit
lands, this package is approved-pending-adoption.
Invariant numbers below refer to the 13-item list in CLAUDE.md.
Last verified state: Phase 13 complete, deployed, browser-verified.
Sunk cost is not an invariant; this roadmap supersedes ROADMAP.md
"Future Product Phases" ordering.

Decision rule: fewer, higher-value phases. Each phase must change what the
user can actually do or trust. Implementation owner is Codex unless stated.
Design owner and final review owner is Fable for every phase.

---

## Phase 14 — State-Machine Hardening

DECISION: Close the final-state downgrade gap before any new capability.
WHY NOW: Invariants 3–4 ("final states never downgrade") are claimed in
docs and relied on by tests, but `PATCH /decisions/requests/{id}/status`
→ `update_decision_request_status()` (shared/services/
decision_request_service.py:56-68, backend/app/main.py:615-628) has no
guard and no test. Every later phase builds on trusting final states.
USER VALUE: Trust. Approved/rejected records cannot be silently reverted.
ARCHITECTURAL VALUE: One canonical transition validator all writers share.
IN SCOPE: The smallest guard that closes the gap — a terminal-state
check in update_decision_request_status (human_approved, rejected,
archived accept no outgoing transitions except
human_approved/rejected → archived); 4xx error on violation; regression
tests for terminal-state preservation. This is a single-user system:
a guard clause plus focused tests, NOT a general transition-matrix
framework for writers that do not exist.
OUT OF SCOPE: New states; a canonical transition-table abstraction;
DecisionLog changes; frontend changes; removing the PATCH endpoint
(guard it, keep it).
DEPENDENCIES: none.
EXPECTED LAYERS: shared/services, backend/app/main.py (error mapping),
tests.
MUST NOT CHANGE: models, migrations, frontend, phistyle_platform,
services/llm_router, scripts.
MIGRATION: none. A migration requirement is a STOP.
KEY INVARIANTS: 3, 4, 8, 11.
STOP CONDITIONS: any schema change; any change to human_review_service
semantics; discovery of other unguarded writers (report, don't fix ad hoc).
ACCEPTANCE: pytest green incl. new transition-matrix tests; PATCH of a
human_approved request to draft returns 4xx and leaves state unchanged.
MANUAL VERIFICATION: curl the PATCH endpoint against a finalized local
decision; confirm 4xx + unchanged state.
CONFIDENCE: HIGH.
RESEQUENCE IF: the endpoint turns out to be unused by anything — then
deletion becomes an acceptable alternative implementation (still Phase 14).

## Phase 15 — Brain v1: LLM-Backed BrainReview (advisory)

DECISION: Replace the deterministic BrainReview *content* with a real
DeepSeek-backed review, keeping deterministic rules as safety gate and
fallback.
WHY NOW: The Brain is the product's namesake and is an if/elif stub
(phistyle_platform/runtime/runtime.py:413-515). DeepSeek is already wired
and tested (providers/deepseek.py). This is the cheapest step from
"diary" to "intelligence" — no new data sources, minimal schema impact.
USER VALUE (stated honestly): an articulate, model-generated critique of
the user's own question+context — challenge of assumptions, unstated
risks, missing considerations. It is NOT evidence-grounded: it cites no
prices, news, or filings until Phase 18. It upgrades rationale quality,
not information content. If the user prefers evidence-first, Phases 15
and 16 may be swapped — say so at ticket time.
ARCHITECTURAL VALUE: Establishes the runtime LLM call pattern (strict
JSON contract, validation, fallback, dry-run) that phases 17–18 reuse.
IN SCOPE: BrainOrchestrator calls DeepSeek (role: deep reasoner) with a
strict JSON output contract (recommendation, rationale, confidence,
risks); deterministic rules still run first and act as a binding floor
with this EXACT enforceable rule: if the deterministic recommendation is
anything other than `proceed`, it is kept as the stored recommendation
(the LLM may only enrich rationale/risks/confidence); only when the
deterministic recommendation is `proceed` may the LLM replace it, and
with any value. No conservatism ordering needs inventing;
`required_human_approval` stays hardcoded True; on any LLM/parse
failure, fall back to current deterministic output; store
`llm_backed: true/false` plus fallback reason and provider/model/token
metadata, and SHOW llm_backed + fallback reason on the decision detail
page so the user can audit when intelligence actually ran; dry-run safe
without API key.
OUT OF SCOPE: Triage stays deterministic (it's a cheap gate — correct as
is); evidence retrieval; Fable provider; prompt-tuning UI; streaming.
DEPENDENCIES: Phase 14.
EXPECTED LAYERS: phistyle_platform/runtime (BrainOrchestrator),
capital_decision_support_service (pass-through of metadata), tests.
MUST NOT CHANGE: state machine, human_review_service,
brain_decision_link_service idempotency, frontend business logic.
MIGRATION: EXPECTED — at most one additive migration on brain_reviews
(nullable columns for model/provider/usage metadata). Anything beyond
additive nullable columns is a STOP.
KEY INVARIANTS: 1, 2, 5, 9.
STOP CONDITIONS: LLM output would drive a state transition directly;
any urge to auto-create HumanReview; schema needs beyond stated.
ACCEPTANCE: tests prove (a) LLM path parses and stores a valid review,
(b) the floor rule exactly as stated above, (c) fallback on malformed
output, (d) pipeline idempotency unchanged, (e) dry-run works keyless,
(f) llm_backed/fallback reason visible via API and UI.
MANUAL VERIFICATION: create a real decision in the browser, Run Analysis
with DEEPSEEK_API_KEY set, confirm non-canned rationale and metadata.
CONFIDENCE: HIGH.
RESEQUENCE IF: DeepSeek quality is unusable for this task → swap provider
decision escalates to Fable before proceeding.

## Phase 16 — Watchlist & Evidence Snapshot v0

DECISION: First real investment data. A watchlist of tickers and an
explicit "fetch evidence" action that snapshots price + headlines into
KnowledgeDocument records linked to a DecisionRequest.
WHY NOW: Reviews without evidence are opinions. This activates the
dormant Knowledge layer (shared/models/knowledge.py) and the dormant
`related_knowledge_document_id` link with real content.
USER VALUE: A decision page shows the actual market context the review
was based on, permanently recorded.
ARCHITECTURAL VALUE: Knowledge layer goes from scaffold to load-bearing;
establishes the external-data-source pattern (read-only, snapshot,
attributed, timestamped).
IN SCOPE: watchlist table + CRUD + minimal UI; one price source and one
headlines source — SOURCE SELECTION IS A FABLE DECISION: Haiku/Explore
gathers factual candidates (availability, rate limits, ToS, cost),
Fable selects the concrete sources in the ticket before Codex starts;
Codex's job is "integrate source X with this interface", nothing more;
explicit fetch (button / endpoint), never automatic background polling
yet; snapshots stored as KnowledgeDocument with source attribution;
decision detail page shows linked evidence.
OUT OF SCOPE: scheduled ingestion (Phase 17); embeddings/RAG; filings
parsing; portfolio sync; LINE alerts.
DEPENDENCIES: Phase 14 (trust), not Phase 15 (parallelizable, but ship
after 15 to keep review scope small).
EXPECTED LAYERS: shared/models (new watchlist model), shared/services,
backend routes, frontend capital pages, migrations, tests.
MUST NOT CHANGE: decision state machine, human review, triage.
MIGRATION: EXPECTED — one migration (watchlist table; possible nullable
evidence-link fields). Data migrations are a STOP.
KEY INVARIANTS: 2, 8, 10 (active PostgreSQL on Mac mini only; NAS only
for cold exports).
STOP CONDITIONS: source requires paid contract or credentials the user
hasn't provided; scope grows toward background jobs.
ACCEPTANCE: fetch → documents persisted with source+timestamp; re-fetch
creates new snapshots without mutating old ones; decision page renders
evidence; pytest green.
MANUAL VERIFICATION: browser: add ticker, fetch, see evidence on a
decision.
CONFIDENCE: MEDIUM-HIGH (source selection is the main unknown).
RESEQUENCE IF: no acceptable free/cheap data source exists → user
decision on paying for data comes first.

## Phase 17 — Materiality Brief v1 (scheduled)

DECISION: A daily scheduled job scans watchlist evidence and produces a
brief listing ONLY events judged material to decisions — the README's
core mission made real.
WHY NOW: First daily-value surface. Requires 15 (LLM pattern) + 16 (data).
USER VALUE: Every morning: "what changed that matters", not a news dump.
IN SCOPE: scheduled execution on the Mac mini — the mechanism (cron vs
compose-level) is a FABLE DECISION made in the ticket, informed by
Haiku-gathered facts; the in-repo scheduler stub may be implemented
minimally for this; ingest fresh snapshots for
watchlist; LLM materiality triage (DeepSeek) with strict JSON contract;
brief persisted + rendered on a dashboard page; explicit "nothing
material today" is a valid and expected output.
OUT OF SCOPE: LINE/push delivery (later, trivial once brief exists);
per-event alerting; intraday.
DEPENDENCIES: Phases 15, 16.
MIGRATION: EXPECTED — one additive migration (brief/brief_item tables).
KEY INVARIANTS: 2, 3, 4; scheduled job is read+write of its own tables
only — it never touches decision states.
STOP CONDITIONS: job needs to modify DecisionRequest/DecisionLog; rate
limits force architecture change.
ACCEPTANCE: job runs idempotently per day; brief page renders; forced
empty day renders correctly; pytest green.
MANUAL VERIFICATION: trigger job manually on Mac mini, view brief in
browser next to real dated snapshots.
CONFIDENCE: MEDIUM.
RESEQUENCE IF: Phase 16 source quality is too poor for materiality
judgment → improve sources first.

## Phase 18 — Evidence-Grounded Brain v2

DECISION: BrainReview must read linked evidence and recent material
events for the tickers involved, and cite what it used.
USER VALUE: Reviews grounded in current reality, with visible citations.
IN SCOPE: Brain reads KnowledgeDocuments linked to the request + recent
brief items for related tickers; rationale cites evidence IDs; UI shows
citations.
OUT OF SCOPE: vector search; cross-decision memory (Phase 20).
DEPENDENCIES: 15, 16 (17 desirable).
MIGRATION: none expected; STOP if needed.
CONFIDENCE: MEDIUM-HIGH.

## Phase 19 — Decision Outcome Tracking

DECISION: Record what actually happened after finalized decisions.
WHY: Turns the diary into a compounding asset; precondition for ever
discussing execution (system-strategy.md §5).
USER VALUE: "Was I right?" becomes answerable; review-after-N-days queue.
IN SCOPE: outcome record (one per finalized DecisionLog, append-only
corrections), review-due queue on dashboard, simple stats (approved vs
outcome).
OUT OF SCOPE: backtesting, P&L integration, portfolio sync.
DEPENDENCIES: none hard (could move earlier if 16/17 block on data
sources).
MIGRATION: EXPECTED — one additive migration.
KEY INVARIANTS: outcome records never mutate decision states.
CONFIDENCE: HIGH on value, MEDIUM on schema details.

## Phase 20 — Memory-Informed Reviews (reassess before starting)

DECISION: Provisional. Brain v2 additionally reads the user's past
decisions + outcomes for related tickers. AgentMemory table becomes live.
REASSESS: after Phase 19 ships, with real usage data. Do not start
without a fresh Fable decision.
CONFIDENCE: LOW (may be merged into 18/19 or dropped).

---

## Delayed / frozen / abandoned

- FROZEN: Phase 2.5 local model serving; all 7 stub providers; App
  Registry future apps (points-wallet, dental-ppt, travel, snowboard);
  AgentRuntime generalization; multi-agent workflows; knowledge graph.
- DELAYED until after Phase 19: backtests, portfolio tracking, risk
  alert rules, LINE delivery.
- ABANDONED: routing the capital pipeline through AgentRuntime for
  purity; `/platform/` directory (delete opportunistically); "many
  providers" as a goal.
- EXECUTION LAYER: not on this roadmap at all. Preconditions in
  system-strategy.md §5.

## Reassessment triggers

Re-open sequencing (a Fable session) if: Phase 16 has no viable data
source; DeepSeek quality blocks Phase 15; the user prefers evidence
before intelligence — then swap 15 and 16 (both orderings are
defensible; 15-first was chosen because it is smaller and establishes
the LLM pattern, not because it is more valuable); the user's actual
usage shows the brief (17) matters more than decision reviews (15);
any invariant must change; three consecutive phases slip on the same
root cause.
