# Ticket: Phase PW-2 — Award Cost Engine

VERDICT: ACCEPTED (Fable, 2026-07-07; commits 610d181 + 64ef79c).
A1-A9 complete; threshold-block fixture (30k miles = exactly 75k
Marriott) passing; migration 0010 (final, incl. source_url) approved.
VERIFIED after: deploy + upgrade 0010_pw_award_cost + user evaluates
one real quote and confirms lots untouched.
OUTSTANDING (separate Codex task, prompt already issued): Excel rates
extraction command (data-rescue/wanlitong_rates.xlsx → dry-run review
list → --commit), honesty rules apply (skip ambiguous, never guess).

FABLE-APPROVED: yes (2026-07-06). PRE-START: fresh-context Sonnet
clarity review recommended; user may waive (record in report).
IMPLEMENTATION OWNER: Codex. VERDICT: new Fable session.
DEPENDS ON: PW-1 ACCEPTED (done) + user's real-import verification.
Binding spec: docs/strategy/point-wallet-master-spec.md §Cost engine.

## 1-2. WHY / USER VALUE

The soul of the wallet: enter one award ticket (program, miles, taxes,
cash price) → ranked list of every way to pay for it with TRUE TWD
cost — existing miles at real lot cost, transfer chains with bonus
math, purchase offers, or just buying the cash ticket.

## 3. STRATEGIC DECISIONS ALREADY MADE (do not reopen)

- EVALUATION IS READ-ONLY. Computing scenarios NEVER mutates
  cost_lots, ledger_transactions, or balances. Lot consumption is
  simulated FIFO in memory. (Recording an actual redemption stays a
  manual ledger entry; automation of that is a later phase.)
- Methods are PURE, no mixed funding in v0:
  A existing miles in the target program (feasible only if balance ≥
    required; cost = simulated FIFO consumption of that account's
    lots; points without lots cost 0 and the scenario is flagged
    "partial cost basis").
  B/C transfer chains, depth ≤ 2 hops, built ONLY from transfer_rules
    rows valid on evaluation date; source funding = existing points
    of ONE account (simulated FIFO). Chains never mix owners (Kent's
    points cannot become Wife's scenario leg).
  D official/promo purchase_offers (kind=official|promo) active on
    evaluation date: cost = required_points ÷ (1+bonus_pct/100) ×
    base_price, converted via latest fx_rates.
  E third_party purchase_offers, same math.
  F cash ticket price (entered on the quote).
- Transfer math (exact): points_received = floor(points_sent ×
  ratio_to/ratio_from × (1+bonus_pct/100)); points_sent must be a
  multiple of ratio_from and ≥ min_transfer; required send = smallest
  valid multiple such that received ≥ required. Two-hop chains apply
  this per hop in sequence.
- Taxes: converted to TWD via latest fx_rates row for the tax
  currency; no rate → use exchange_rate_service fetch; still none →
  scenario carries a "missing fx rate" warning and shows tax
  unconverted.
- Every scenario persists: method, full path_json (each hop: from,
  to, sent, received, rule id, bonus; each lot consumed: lot id, qty,
  cost), true_cost_twd (points cost + taxes TWD), saving_vs_cash_twd,
  rank. funding_scenarios rows are immutable snapshots per evaluation
  run; re-evaluating creates a new run set (runs idempotent per
  identical quote+date? NO — rates/lots change; each explicit
  evaluation is a new timestamped run).
- Both owners' accounts are enumerated; each scenario is tagged with
  its owner.

## AMENDMENT (Fable, 2026-07-07 — 依使用者萬里通成本邏輯重述,
## 覆蓋前述任何牴觸條款)

A1. 新增方法 B+:「當日購入來源點數 → 轉點鏈」。來源計畫(如
  萬里通)若有有效 purchase_offer,引擎必須評估「現買現轉」路徑:
  成本 =(實付金額+手續費−回饋)÷ 實際入帳點數(含贈點)×
  所需來源點數,再經轉點鏈。§3「methods are PURE」放寬為:
  單一來源購買+單一轉點鏈 = 合法方法;仍禁止多來源混搭。
A2. purchase_offers 增欄(同一 migration 內):paid_amount、fees、
  rebate、points_received(皆 NULL 可空);四欄齊備時系統自動算
  每點真實成本 =(paid+fees−rebate)÷points_received,取代
  base_price;贈點一律算進分母。
A3. transfer_rules 增欄:rule_kind Text NOT NULL DEFAULT 'linear'
  (linear|threshold_block)、block_size、block_bonus_points(NULL)。
  threshold_block 語義(Marriott 型):每滿 block_size 送
  block_bonus_points,餘量按基礎比例無加成,需求反算必須分段。
  必測 fixture:60k Marriott→25k miles 規則下,需 30,000 miles
  → 恰好 75,000 Marriott(60k 段 25k + 15k 段 5k),斷言到點。
A4. Bonus 一律套在「實際最終取得數」上(分母),不是備註。
A5. 情境輸出增列並顯示:effective_cpp、total_cash_cost_twd、
  points_acquired、points_consumed、points_leftover。排名依
  total cost(完成這張票的總成本),leftover 為資訊欄不進排名。
A6. 每個 quote 對每個可行 program 至少跑三種成本來源:既有點數
  (lot 真實成本)、當日萬里通路徑(A1)、官方/第三方買分。

A7. 轉點規則頁 UI 改為「依來源計畫分頁」:萬里通/萬豪/吉祥/
  Qatar/漢莎/LifeMiles…(分頁 = from_program 的 group-by,動態
  產生,無 schema 影響)。對齊使用者 Excel 的心智模型。
A8. transfer_rules 與 purchase_offers 各增 source_url Text NULL
  (併入 migration 0010):存放比例出處連結,UI 顯示為可點的
  「查證」連結。自動上網抓取比例 = NO-GO(TripPlus 教訓:脆弱
  爬蟲不做);比例由使用者手動維護,配 valid_from/until。
A9. 買分階梯價(如 AS 特賣 0.54/0.58/0.62/0.66 per mile)用多筆
  purchase_offers 表達(每階一筆,min/max_points 區分),不新增
  階梯結構。

## 5/7. SCOPE + SCHEMA (one additive migration, id ≤ 32 chars)

- award_quotes: id PK; origin Text NULL; destination Text NULL;
  travel_date Date NULL; cabin Text NULL; pax Integer NOT NULL
  DEFAULT 1; program_id FK RESTRICT NOT NULL; miles_required
  Numeric(18,0) NOT NULL; taxes_amount Numeric(18,2) NULL;
  taxes_currency Text NULL; cash_price_twd Numeric(18,2) NULL;
  source Text NOT NULL DEFAULT 'manual'; created_at.
- funding_scenarios: id PK; award_quote_id FK CASCADE NOT NULL;
  evaluated_at timestamptz NOT NULL; owner Text NOT NULL; method Text
  NOT NULL (existing|transfer_chain|purchase_official|
  purchase_third_party|cash); path_json Text NOT NULL; true_cost_twd
  Numeric(18,2) NOT NULL; saving_vs_cash_twd Numeric(18,2) NULL;
  rank Integer NOT NULL; warnings Text NULL.
- Service: award_cost_engine.py (pure functions; engine core takes
  plain data in, scenarios out — unit-testable without DB).
- Routes additive: quote CRUD, POST evaluate, GET scenarios per quote.
- Frontend: /wallet/awards — quote form, evaluate button, ranked
  comparison table (winner highlighted, savings vs cash), path
  detail expansion.
- Tests: HAND-COMPUTED fixture mandatory — a fixture wallet (two
  owners, lots with known costs, 萬里通→airline rule with bonus,
  萬里通→Marriott→airline two-hop incl. the 60k→25k pattern as
  transfer_rules rows, one official offer, fx rates) and a quote
  whose FULL expected scenario list (costs to the cent, ranks) is
  written out in the test and asserted exactly. Plus: read-only proof
  (lots unchanged after evaluate), infeasible-balance exclusion,
  min_transfer rounding, expired-rule exclusion, missing-fx warning.

## 6/8. OUT OF SCOPE / MUST NOT CHANGE

seats.aero (PW-3); notifications; LLM; mixed funding; depth>2;
actual redemption booking/recording automation; mutating any PW-1
table from the engine; decision pipeline; trading tables; llm_router.

## 15. STOP (additional)

Any engine write path to lots/ledger; chain enumeration exploding
(>200 scenarios per quote → report, don't truncate silently); schema
beyond §5.

## 14. MANUAL VERIFICATION (user)

Enter a real award you're considering (e.g. TPE→TYO J ×2 on a real
program), evaluate, hand-check the winner's math against your own
calculation; confirm balances/lots unchanged afterward.

## 16. COMPLETION REPORT

Standard + migration pasted + the hand-computed fixture's expected
table reproduced in the report.
