# Ticket: Phase 18 — Backtest Engine v0 (swing, daily bars)

FABLE-APPROVED: yes (2026-07-06, written at session close; PRE-START:
fresh-context Sonnet clarity review required before Codex begins).
IMPLEMENTATION OWNER: Codex. REVIEW: Sonnet. VERDICT: new Fable
session. DEPENDS ON: Phase 17 ACCEPTED.
USER INPUT REQUIRED BEFORE CODEX STARTS: the user's actual futures
brokerage fee per contract (凱基) — without it the ticket uses the
placeholder below and every result page must show "fee = placeholder".

VERDICT: ACCEPTED (Fable, 2026-07-09; commit d21d946). Migration
0015_backtest_engine approved. Tax rate cited to 法規資料庫.
Known limitations logged (close-only stops, qty=1, placeholder fee —
replace fee when user provides KGI schedule). VERIFIED after deploy
+ 0015 + one real spec run. Roadmap 14-19 now ALL ACCEPTED.

PRE-START SONNET REVIEW: COMPLETED 2026-07-09(2 BLOCKER+4 HIGH,
全數由 AMENDMENT 解決)。AMENDMENT 優先於原文,逐字實作。

## AMENDMENT (Fable, 2026-07-09 — BINDING)

C1 策略 spec JSON(唯一合法形狀):
  {name, market:"taifex"|"us", symbol, direction:"long"|"short",
   start_date?, end_date?, entry:RULE, exit:{stop_pct?, target_pct?,
   time_exit_days?, opposite_signal:bool}}
  RULE 四型:
  {type:"sma_cross", fast:int, slow:int}——close 的 SMA(fast)
    上穿 SMA(slow) 觸發 long 進場;下穿觸發 short。
  {type:"price_vs_sma", n:int, side:"above"|"below"}——close 穿越
    至該側當日觸發。
  {type:"breakout", n:int}——long:close > 前 n 日最高 high;
    short:close < 前 n 日最低 low。
  {type:"inst_net", product:"TX"|"MTX"|"TMF", identity:"foreign"|
    "trust"|"dealer", op:">"|"<", threshold:int}——當日該法人
    net_contracts 滿足條件觸發(僅 taifex)。
  執行時點(v0 確定性簡化,文件標明):訊號以 t 日收盤計算,
  成交價 = t 日 close ± 滑價;stop/target 以後續每日 close 檢查
  (不看盤中高低,已知限制)。
C2 walk-forward:區間 = spec 宣告範圍,未宣告則用該 symbol 可用
  bars 全range;前 70% 交易日 = in-sample、後 30% = out-of-sample,
  同參數各跑一次。decay_ratio = oos_expectancy / is_expectancy
  (is_expectancy ≤ 0 時顯示 n/a)。
C3 成本:期交稅基 = 指數 × 點值 × 口數,每邊課稅;fixture 稅率
  用 0.00002,實際稅率 Codex 查證引用。US 滑價基 = price × shares
  × 0.0005/邊。淨損益 = 毛損益 −(手續費+稅+滑價)×2邊。
C4 指標公式:equity curve = 逐筆平倉淨損益累加;max_drawdown =
  equity 峰谷最大落差;expectancy = 淨損益均值/筆;win_rate =
  獲利筆數/總筆數。TWD 與 USD 永不相加。
C5 §9 MIGRATION EXPECTED:一個 additive,id ≤32:
  strategy_specs(id PK; name Text NOT NULL UNIQUE; market/symbol/
  direction Text NOT NULL; spec_json Text NOT NULL; created_at tstz
  NOT NULL default now)、backtest_runs(id PK; strategy_spec_id FK
  RESTRICT NOT NULL; range_start/range_end Date NOT NULL;
  spec_snapshot_json/cost_params_json/results_json Text NOT NULL;
  run_hash Text NOT NULL UNIQUE; created_at)。冪等鍵 = run_hash =
  sha256(spec_snapshot+range+cost_params),命中即回既有 run。
C6 trade_plans.strategy_spec_id 的 FK 約束:本 phase OUT OF SCOPE
  (維持 Integer 無約束,列入未來 janitorial)。
C7 新頁面必須加入 frontend/app/page.tsx 的 LAUNCHER_TILES:
  🧪 回測(/capital/backtests)。

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
