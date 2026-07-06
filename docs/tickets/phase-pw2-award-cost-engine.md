# Ticket: Phase PW-2 — Award Cost Engine

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
