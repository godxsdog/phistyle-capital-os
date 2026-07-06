# Ticket: Phase 18 — Backtest Engine v0 (swing, daily bars)

FABLE-APPROVED: yes (2026-07-06, written at session close; PRE-START:
fresh-context Sonnet clarity review required before Codex begins).
IMPLEMENTATION OWNER: Codex. REVIEW: Sonnet. VERDICT: new Fable
session. DEPENDS ON: Phase 17 ACCEPTED.
USER INPUT REQUIRED BEFORE CODEX STARTS: the user's actual futures
brokerage fee per contract (凱基) — without it the ticket uses the
placeholder below and every result page must show "fee = placeholder".

## 3. STRATEGIC DECISIONS ALREADY MADE

- Deliberately MINIMAL rule engine. v0 strategy spec (JSON, stored):
  {name, market, symbol, direction rules}: entry/exit conditions
  composed ONLY from: SMA(n) cross / price vs SMA(n); N-day
  high/low breakout; 三大法人 net position (per identity) sign or
  threshold (taifex only). Exits additionally: stop_pct, target_pct,
  time_exit_days, opposite_signal. NOTHING ELSE in v0 — new indicator
  requests = STOP (they arrive as later tickets, this is the
  overfitting guardrail).
- NO parameter optimization/sweeps in v0. The engine runs the spec as
  given, once. Automated search = STOP.
- Cost model per instrument class, defaults SHOWN on every result:
  TAIFEX futures per side: brokerage TWD 50/口 placeholder (replace
  with user's real fee schedule when provided), 期交稅 = taxable rate
  per current TAIFEX/MoF rules — Codex verifies the current index
  futures transaction tax rate at implementation and cites the source
  in the completion report; slippage 1 tick/side (TX tick=1pt=NT$200;
  MTX 1pt=NT$50; TMF 1pt=NT$10). US: commission $0, slippage
  0.05%/side, results in USD with an explicit "TWD conversion not
  applied" label.
- Contract awareness: point values above; position size in contracts
  (futures) or shares (US); margin NOT modeled in v0 (documented
  limitation) — P&L is per-contract mark-to-market.
- Walk-forward: chronological in-sample/out-of-sample split, default
  70/30, both windows' metrics + decay ratio reported. A run without
  out-of-sample is not a valid run.
- backtest_runs are IMMUTABLE (invariant 7 spirit): spec snapshot,
  data range, cost assumptions, results JSON, created_at. Re-running
  identical spec+range+costs = idempotent (return existing run).
- LLM: optional spec-drafting only, in a service (NOT runtime.py),
  Phase 15 call pattern, output clearly labeled draft; the engine
  itself is 100% deterministic. LLM free text → Text columns only.
- Metrics per run: trade list, equity curve points, net P&L, max
  drawdown, win rate, expectancy, exposure days, trade count, in/out
  sample decay. All computed deterministically; hand-verified
  fixture required.

## 5/7. SCOPE

shared/models/backtest.py (strategy_specs, backtest_runs — full
column specs analogous to Phase 16 style; one migration, id ≤ 32
chars); shared/services/backtest_service.py (+ optional
strategy_draft_service.py for LLM); additive main.py routes; frontend
/capital/backtests pages (list, new-run form, result view — tables,
no chart lib); tests.

## 6/8. OUT OF SCOPE / MUST NOT CHANGE

Intraday; options; portfolio-of-strategies; ML; optimization; margin
modeling; order placement of any kind. Decision pipeline, Phase 16/17
tables (read-only reads of market_daily_bars/institutional_positions
are allowed and expected), services/llm_router.

## 13. ACCEPTANCE

Reference fixture: a tiny synthetic bar series + a simple SMA-cross
spec whose trades and P&L (incl. costs) are hand-computed in the test
file, asserted exactly. Walk-forward split correctness test.
Idempotent re-run test. Immutability test (no UPDATE path exists).
pytest green in .venv.

## 14. MANUAL VERIFICATION (user)

Run one real spec on real ingested TX data end-to-end in the browser;
spot-check 2-3 trades against the daily bars; confirm cost lines
visible.

## 15. STOP (additional)

New indicators; optimization; margin; missing fee schedule blocking
honesty (proceed with placeholder + label instead); any write to
market data or decision tables.

## 16. COMPLETION REPORT

Standard + migration pasted + cited source for the futures
transaction tax rate.
