# Ticket: Phase 19 — Trade Plan Pipeline (paper-first decision loop)

FABLE-APPROVED: yes (2026-07-06, written at session close; PRE-START:
fresh-context Sonnet clarity review required before Codex begins —
this is the largest ticket, expect findings; BLOCKERs go to a new
Fable session).
IMPLEMENTATION OWNER: Codex. REVIEW: Sonnet. VERDICT: new Fable
session. DEPENDS ON: Phases 15 (VERIFIED) + 17 ACCEPTED; 18 desirable
but not blocking.

VERDICT: ACCEPTED (Fable, 2026-07-09; commit 0b27129). Migration
0014_trade_plans approved. STOP re atomicity resolved via option 2
(commit=True param, rollback-proof test). VERIFIED after user deploy
+ 0014 + live paper plan round-trip. Precedent logged: when a spec
demands atomicity, always check reused helpers' commit behavior.

PRE-START SONNET REVIEW: COMPLETED 2026-07-09(2 BLOCKER + 2 HIGH,
全數由下方 AMENDMENT 解決)。Codex may start;AMENDMENT 優先於原文。

## AMENDMENT (Fable, 2026-07-09 — BINDING)

B1(建立流程,原文未定):新端點 POST /capital/trade-plans =
  單一原子交易:先跑 R1-R3 風控檢查 → 呼叫既有
  create_capital_decision_request(risk_level:有任何違規="high",
  全過="medium";question/context 由計畫欄位組字)→ 同交易寫入
  trade_plans 列(含 risk_check JSON)。失敗全回滾。分析仍走
  既有 POST /capital/decisions/{id}/run,不重做。禁止在
  decision_request_service 加 risk_level 修改器(§8 禁改)。
B2(plan_outcomes 補欄):加 holding_days Integer NULL、
  planned_vs_actual Text NULL(JSON)、currency Text NOT NULL。
B3(損益公式與幣別):futures:gross_pnl =(exit−entry)×
  點值(TX 200/MTX 50/TMF 10 TWD)× 口數 × 方向正負,currency
  ='TWD';US:(exit−entry)× 股數 × 方向正負,currency='USD'。
  統計頁「永不混幣別」:TWD 與 USD 分區各自顯示勝率/期望值,
  不做匯率換算。
B4(標準補節):§4 CONTRACTS:MTM 掛載點=backend/app/commands/
  ingest_market_data.py(讀 market_daily_bars close,symbol 命名
  與 market_data_service TX/MTX/TMF 一致);Phase 14/15 行為不變。
  §9 MIGRATION EXPECTED:一個 additive(trade_plans/plan_marks/
  plan_outcomes 三表),id ≤32 字元,報告貼全文。§10:不得觸碰
  任何既有狀態轉移。§11:MTM 冪等 per (plan, mark_date);
  重跑管線不重建計畫。§12:MTM 缺 bar 跳過記 log 不炸;
  LLM 失敗走 Phase 15 既有 fallback。

## 1-2. WHY / USER VALUE

Converts the existing decision spine into the trading discipline
loop: every trade (paper by default) = structured plan → deterministic
risk check + LLM critique → explicit approval → daily mark-to-market →
recorded outcome → running stats. Directly targets how the user
previously lost money (no stops, size drift, no review).

## 3. STRATEGIC DECISIONS ALREADY MADE

- A trade plan IS a DecisionRequest (app=capital, type=investment)
  plus a trade_plans row FK'd to it. The existing pipeline
  (triage → brain → decision log → human review) is REUSED, not
  duplicated. Approval stays record-only (invariant 2) — paper
  position "opens" only as a record.
- Plan fields: market (taifex|us), symbol, direction (long|short),
  planned_entry, stop_price (MANDATORY), target_price NULL, quantity
  (contracts|shares), declared_capital_twd (carried on the plan),
  thesis Text, strategy_spec_id FK NULL (links Phase 18), is_paper
  Boolean NOT NULL DEFAULT true.
- DETERMINISTIC RISK RULES (checked at plan creation, results stored
  and fed into the Brain prompt; violations DO NOT block creation —
  they force triage risk_level=high so the pipeline demands human
  review, and are listed in the review):
  R1 risk_per_trade = |entry−stop| × point_value × qty (futures;
  point values: TX 200, MTX 50, TMF 10 TWD/pt) or |entry−stop| × qty
  (US, USD, labeled unconverted) must be ≤ 1% of
  declared_capital_twd (US rule applies a fixed disclosed 32 TWD/USD
  placeholder rate, shown on screen).
  R2 stop must be on the loss side of entry for the direction.
  R3 quantity > 0; declared_capital_twd > 0.
- Approved plans are IMMUTABLE (edits = new plan; the old one is
  closeable only). Terminal-state invariants 3-4 apply unchanged.
- Brain critique: existing Phase 15 BrainOrchestrator path, with plan
  fields + risk-rule results injected into the prompt context (the
  service composes the context string; runtime.py may gain ONLY an
  optional extra input field passed through to the prompt — no logic
  change, floor rule untouched).
- Daily mark-to-market: extends the Phase 17 cron command; for each
  open (approved, un-closed) plan, record close price of that day
  from market_daily_bars into plan_marks. Missing bar = skip + ingest
  log entry, never crash.
- Closing: explicit user action (close price + datetime, defaulting
  to latest mark) → plan_outcomes row (append-only): exit_price,
  gross_pnl, planned_vs_actual (stop respected? exit beyond stop?),
  holding_days. Outcomes NEVER mutate decision states (they reference
  them).
- Stats endpoint/page: closed-plan count, win rate, expectancy,
  plan-adherence rate (stop respected & size within rule), paper vs
  real split. These numbers feed the Phase 20 gate.

## 5/7. SCOPE + SCHEMA (one migration, id ≤ 32 chars)

- trade_plans: id PK; decision_request_id FK UNIQUE NOT NULL ondelete
  RESTRICT; fields per §3 (prices Numeric(18,6), quantity
  Numeric(18,4), declared_capital_twd Numeric(18,2)); risk_check
  Text NOT NULL (JSON results); created_at.
- plan_marks: id PK; trade_plan_id FK CASCADE; mark_date Date;
  close_price Numeric(18,6); UNIQUE(trade_plan_id, mark_date).
- plan_outcomes: id PK; trade_plan_id FK RESTRICT UNIQUE; exit_price;
  exit_at; gross_pnl Numeric(18,2); stop_respected Boolean; notes
  Text NULL; created_at. Append-only (corrections: new row is NOT
  allowed — UNIQUE forces one outcome; a correction is a new plan?
  NO: corrections go in notes; the number stands. This is the
  unfalsifiability rule.)
- Services: trade_plan_service.py (create+risk rules, list, close),
  MTM logic in the Phase 17 ingest command. main.py ADDITIVE routes.
  Frontend: plan form, open-plans list with marks, close action,
  stats page. Human review UI is the EXISTING approve/reject flow.

## 6/8. OUT OF SCOPE / MUST NOT CHANGE

Broker APIs, order placement, alerts, options, intraday marks,
auto-close at stop (the system never trades — a hit stop shows in
marks and stats, the user closes it). human_review_service,
brain_decision_link_service, decision_request_service guards,
Phase 14 transition rules, llm_router.

## 13. ACCEPTANCE

Risk rules: each of R1-R3 violation and pass cases; violation forces
high risk → human_review_required path. Immutability: no update
route for approved plans. Full loop fixture: create → run pipeline →
approve (existing flow) → marks over 3 fixture days → close →
outcome + stats hand-verified. Idempotent MTM per date. Existing
pipeline/final-state tests green unmodified. pytest green in .venv.

## 14. MANUAL VERIFICATION (user)

One real paper plan through the browser across ≥2 market days:
create, see critique cite the risk numbers, approve, watch marks
appear after ingest, close it, see stats update.

## 15. STOP (additional)

Any pressure toward auto-execution/auto-close; schema beyond §5;
changes to the floor rule or approval semantics; MTM needing intraday
data.

## 16. COMPLETION REPORT

Standard + migration pasted.
