# Current Roadmap — Approved Phases 14–20 (v2, trading redirect)

Status: APPROVED (Fable G0 2026-07-04; REDIRECTED 2026-07-05)
REDIRECT DECISION (2026-07-05): the user's actual goal is profitable
swing trading of TAIFEX index futures AND US stocks (capital scale
500k–3M TWD futures-side, horizon days–weeks, prior futures experience
with net losses). ONE pipeline, multiple markets: instruments differ in
data source and cost model, never in pipeline structure. Old
Phases 16–18 (news watchlist, materiality brief, evidence-grounded
brain for stock decisions) are DEFERRED; Phases 16–20 are rebuilt as a
strategy-research pipeline: loss attribution → market data → backtest →
paper-trade loop → live-readiness gate. Phase 15 is unchanged (its LLM
review pattern is exactly what will critique trade plans).
HONESTY CLAUSE (binding on all future agents): no agent may claim or
imply a strategy "will make money". Backtest results are historical
fits until walk-forward + paper validation. The system never places
orders — the user executes manually at the broker (invariant 2).
Invariant numbers refer to the 13-item list in CLAUDE.md.

Decision rule: fewer, higher-value phases. Implementation owner Codex;
design + verdict owner Fable.

---

## Phase 14 — State-Machine Hardening

VERDICT: ACCEPTED + VERIFIED (2026-07-05, commit f2cf216; details in
docs/tickets/phase-14-state-machine-hardening.md).

(Original definition retained in the ticket; terminal DecisionRequest
states are now guarded on all writer paths.)

## Phase 15 — Brain v1: LLM-Backed BrainReview (advisory)

VERDICT: ACCEPTED + VERIFIED (2026-07-06; details in
docs/tickets/phase-15-brain-v1-llm-backed-brainreview.md). Current
phase is now Phase 16. Unchanged by the redirect. Establishes the runtime LLM pattern (strict JSON
contract, deterministic floor, fallback, llm_backed observability)
that Phases 18–19 reuse for trade-plan critique. All original scope,
invariants, and acceptance criteria stand as written in the ticket.

## Phase 16 — Trade History Import & Loss Attribution

DECISION: Before writing any new strategy, import the user's past
futures trades and make the losses legible.
WHY NOW: The user traded futures and lost overall. The cheapest real
edge available today is knowing exactly how the money was lost. This
needs no market data feed, no backtester, and produces immediate value.
USER VALUE: A dashboard answering: P&L by direction, holding period,
entry weekday/time, position-size drift, stop-discipline (did losses
exceed planned stops), overtrading clusters, long-vs-short asymmetry.
Plus an LLM-written narrative attribution (Phase 15 pattern) the user
can challenge.
IN SCOPE: trade-record tables (instrument + market, direction,
entry/exit datetime+price, quantity (contracts or shares), fees, tax,
currency, realized P&L, optional planned stop); CSV import endpoint +
minimal UI covering BOTH the futures broker export and the US
brokerage export (exact column mappings settled in the ticket after
the user provides one sample file per broker); deterministic analytics listed above; one
LLM narrative summary; dashboard page.
OUT OF SCOPE: live broker API connection; automatic sync; market data;
backtesting; any strategy recommendation.
DEPENDENCIES: Phase 15 (LLM pattern) desirable, not blocking.
MIGRATION: EXPECTED — one additive migration (trade_records + import
batch tables). Data migrations = STOP.
KEY INVARIANTS: 2, 8, 10; imported history is append-only — corrections
create new rows, never mutate (mirrors invariant 7's spirit).
STOP CONDITIONS: broker CSV format cannot be mapped without guessing →
STOP and ask the user; any urge to auto-connect to a broker.
ACCEPTANCE: import of the user's sample file round-trips correctly;
re-import of the same file is idempotent (no duplicates); analytics
match hand-computed values on a small fixture; pytest green.
MANUAL VERIFICATION: user imports real history in the browser and
confirms totals match broker statements.
CONFIDENCE: HIGH on value, MEDIUM on CSV-format friction.

## Phase 17 — Market Data Ingestion v0 (TAIFEX + US daily bars)

DECISION: Daily-bar pipeline, two datasets: (a) TAIFEX TX/MTX/TMF from
TAIFEX official published data (free, authoritative), plus 三大法人
positions and settlement calendar; (b) US stock daily OHLCV for the
user's watchlist tickers from ONE free/cheap source — BOTH SOURCES ARE
FABLE DECISIONS, finalized in the ticket after Haiku verifies current
formats/URLs/ToS; Codex integrates exactly what the ticket names.
WHY NOW: Swing trading needs daily bars only — cheap to store, hard to
get wrong, sufficient for the backtester and mark-to-market.
USER VALUE: A permanent local market-data store the backtester and
trade-plan reviews will read; daily auto-update.
IN SCOPE: daily OHLCV + open interest for TX/MTX/TMF; 三大法人 daily
positions; settlement/expiry calendar; US daily OHLCV for a small
user-defined ticker list; historical backfill; scheduled daily fetch on
the Mac mini (mechanism is a Fable decision in the ticket; the in-repo
scheduler stub may be minimally implemented); data-quality checks
(gaps, duplicate dates); TAIFEX ships first if the US source stalls.
OUT OF SCOPE: intraday/tick data; options data; real-time quotes;
fundamentals/news; charting UI beyond a simple sanity table.
DEPENDENCIES: none hard (parallelizable with 16; ship after it).
MIGRATION: EXPECTED — one additive migration (market data tables).
KEY INVARIANTS: 2, 8, 10; the scheduled job writes only its own tables,
never decision/trade state (3, 4).
STOP CONDITIONS: TAIFEX format requires scraping beyond documented
downloads; storage design pushes toward NAS (forbidden, invariant 10).
ACCEPTANCE: backfill loads N years without gaps; daily job idempotent
per date; quality checks flag injected gaps; pytest green.
MANUAL VERIFICATION: spot-check a handful of dates against TAIFEX
website numbers.
CONFIDENCE: MEDIUM-HIGH (format churn is the main unknown).

## Phase 18 — Backtest Engine v0 (swing, daily bars)

DECISION: A deliberately small rule-based backtester with a REALISTIC
cost model, walk-forward evaluation, and an anti-overfitting report.
Correctness over features.
WHY NOW: This is the gate between "idea" and "money". Without honest
costs and out-of-sample discipline, every strategy looks profitable.
USER VALUE: Any rule-based swing idea (the user's or LLM-drafted) gets
an honest verdict: net-of-cost equity curve, max drawdown, in-sample vs
out-of-sample decay, trade count, exposure.
IN SCOPE: declarative strategy spec (entry/exit rules over daily bars +
三大法人 fields; parameters explicit); cost model PER INSTRUMENT CLASS —
futures: brokerage fee + 期交稅 + fixed slippage per side, with
margin/contract-size awareness for TX/MTX/TMF; US stocks: commission +
slippage + an explicit TWD/USD conversion note — concrete default
numbers are set in the ticket and shown in every result; walk-forward
splits; persisted backtest runs (spec + data range + results,
immutable); results page. LLM may DRAFT strategy specs via the Phase 15
pattern, clearly labeled drafts.
OUT OF SCOPE: intraday logic; optimization/parameter search (v1 runs
the spec as given — automated sweeps invite overfitting and wait for a
later decision); portfolio-of-strategies; ML models.
DEPENDENCIES: Phase 17.
MIGRATION: EXPECTED — one additive migration (strategy_specs,
backtest_runs).
KEY INVARIANTS: 2, 8; backtest results are immutable records (7).
STOP CONDITIONS: any pressure to connect the backtester to order
placement; cost-model numbers unavailable → ask user for their actual
broker fee schedule rather than guessing.
ACCEPTANCE: a reference strategy fixture produces hand-verifiable
trades and P&L including costs; walk-forward report renders; rerun of
same spec+range is idempotent; pytest green.
MANUAL VERIFICATION: user runs one simple idea end-to-end and checks a
few trades against a chart.
CONFIDENCE: MEDIUM (engine correctness takes care; scope is small on
purpose).

## Phase 19 — Trade Plan Pipeline (paper-first decision loop)

DECISION: The existing DecisionRequest pipeline becomes the trade-plan
pipeline, absorbing old Phase 19 (outcome tracking). Every trade —
paper or real — starts as a structured plan and ends as a recorded
outcome.
WHY NOW: This converts the system's existing spine (request → review →
approval → record) into the discipline layer that directly targets how
the user previously lost money.
USER VALUE: A trade plan form (instrument + market — TAIFEX futures or
US stock — direction, entry, stop, target, quantity, thesis, strategy
reference); Brain review (Phase 15
pattern) critiques it against deterministic risk rules — default rule
set in the ticket: risk-per-trade ≤ 1% of declared capital, stop is
mandatory, size consistent with margin, no plan may be edited after
approval (new plan supersedes); explicit approval records the plan;
daily mark-to-market from Phase 17 data; outcome recorded at close
(planned vs actual: slippage vs plan, stop respected?); running stats
(win rate, expectancy, plan-adherence rate).
PAPER-FIRST: plans are paper by default. A "real" flag exists for
manually-executed broker trades; the system still never places orders.
IN SCOPE: plan schema on top of DecisionRequest (additive), risk-rule
checks as deterministic floor, mark-to-market job, outcome records
(append-only), stats page.
OUT OF SCOPE: broker API, alerts/notifications (later), options,
intraday plans.
DEPENDENCIES: Phases 15, 17 (18 desirable).
MIGRATION: EXPECTED — additive (trade_plans, plan_outcomes or
equivalent additive columns/tables).
KEY INVARIANTS: 1, 2, 3, 4, 7 — approval is record-only; outcomes never
mutate decision states; no auto-created HumanReview.
STOP CONDITIONS: anything resembling order routing; risk rules being
weakened without a user-authorized ticket change.
ACCEPTANCE: full loop on fixtures: plan → critique → approve → daily
MTM → close → outcome + stats; re-runs idempotent; final states
preserved; pytest green.
MANUAL VERIFICATION: user runs one real paper trade for several days in
the browser.
CONFIDENCE: HIGH on design fit, MEDIUM on schema details.

## Phase 20 — Live-Trading Readiness Gate (reassess; not auto-started)

DECISION: Provisional. Defines the gate, not a feature: live "real"
trades get first-class support only after ALL of: ≥ 30 closed paper
plans; plan-adherence ≥ 90%; documented expectancy net of costs;
backtest + paper results directionally consistent; a written risk
budget (max daily loss, max concurrent contracts) the user signs off.
Until then trading real money is the user's own manual decision outside
the system's endorsement.
REASSESS: after Phase 19 has ≥ 30 closed plans. Fresh Fable decision
required. The system NEVER places orders regardless of this gate.
CONFIDENCE: framework HIGH, thresholds MEDIUM (tune with data).

---

## Delayed / frozen / abandoned

- DEFERRED by the 2026-07-05 redirect: news watchlist + evidence
  snapshots (old 16), materiality brief (old 17), evidence-grounded
  brain for stock decisions (old 18), memory-informed reviews (old 20).
  Revisit only if the user's long-horizon stock decisions return as a
  priority.
- FROZEN: Phase 2.5 local model serving; the 8 stub providers; App
  Registry future apps; AgentRuntime generalization; multi-agent
  workflows; knowledge graph; RAG/vector search.
- ABANDONED: routing the capital pipeline through AgentRuntime;
  `/platform/` directory (delete opportunistically); "many providers"
  as a goal.
- EXECUTION LAYER / order placement: never on this roadmap. Phase 20 is
  a readiness gate for the USER's manual trading, not automation.

## Governance calibration checkpoint (after Phase 14 and 15 verdicts)

At each of the first two phase verdicts, Fable records: extra Fable
interventions (target 0), STOPs and false STOPs, ticket length vs risk,
Codex questions the ticket should have answered. Interventions > 2 or
false STOPs → governance-pruning pass before the next phase (delete or
relax rules only). Phase 14 result: 0 / 0 / proportionate / 0.

## Reassessment triggers

Re-open sequencing (Fable session) if: TAIFEX data formats block Phase
17; DeepSeek quality blocks Phase 15; the user's broker CSV cannot be
obtained for Phase 16 (then start at 17); the user stops trading or
capital scale changes materially; any invariant must change; three
consecutive phases slip on the same root cause.
