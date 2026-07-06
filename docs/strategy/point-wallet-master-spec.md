# Point Wallet Master Spec (PW program)

Status: APPROVED (Fable, 2026-07-06). Source: user's consolidated
analysis of the legacy app (legacy/points-wallet/, verified: app.js
1724 lines, server.py referencing data/points_wallet.json +
config/pingan_wanlitong_rules.json + config/official_purchase_costs
.json — THOSE THREE FILES ARE NOT IN THIS REPO; data rescue required).

## Product definition (binding)

A Points & Miles DECISION ENGINE for two owners (Kent, Wife): it
knows every point held, what each point actually cost (lot-level cost
basis), when it expires, every transfer path (incl. 平安萬里通 rules
with bonuses, Marriott 60k→25k transit), current purchase offers, and
— given a specific award ticket — ranks ALL funding paths (use
existing miles / transfer chains / official or third-party purchase /
cash ticket) by true TWD cost. It records and computes; it never
books, transfers, or stores credentials.

## Architecture decisions (binding)

1. Rebuilt INSIDE phistyle-capital-os as a proper vertical (FastAPI
   routes + Next.js pages + PostgreSQL). The legacy app.js/http.server
   is reference + data source only — never extended.
2. PostgreSQL is the single source of truth. No localStorage store.
3. Derived costs are computed from Ledger + Rules + Rates, never
   hand-stored. Legacy cached cost fields import ONLY as opening
   cost lots.
4. Exchange rates become a SHARED service (shared/services/
   exchange_rate_service.py; open.er-api.com + fallback + daily cache
   table) — other verticals (e.g. backtest USD display) may reuse it.
5. Two owners as a plain owner field; NO login/auth in v0 (LAN trust,
   consistent with the whole OS). Auth is a future platform phase.
6. TripPlus crawler is NOT rebuilt (prior decision stands): third-
   party prices are manual-entry offers.
7. seats.aero via Partner API only; "broader than seats.aero" award
   search remains NO-GO (closed engines, scraping arms race).
8. No LLM until PW-4; the engine is 100% deterministic.
9. Zero coupling to the trading/decision pipeline. Same invariants:
   additive migrations ≤32-char ids, main.py additive-only, no
   credentials, no external actions.

## Domain model (authoritative)

Owner(kent|wife) → enum field, not a table.
programs: id, name UNIQUE, kind(airline|hotel|bank|other),
  expiry_rule_note.
accounts: id, owner, program_id FK, account_ref(masked, optional),
  status, last_activity Date NULL, notes. UNIQUE(owner, program_id).
ledger_transactions: id, account_id FK, kind(earn|buy|transfer_in|
  transfer_out|redeem|expire|adjustment), quantity Numeric(18,2)
  signed, occurred_at Date, counterparty_account_id FK NULL,
  cost_total Numeric(18,2) NULL, cost_currency Text NULL, note.
  APPEND-ONLY.
cost_lots: id, account_id FK, source_transaction_id FK, quantity,
  remaining_quantity, total_cost_twd Numeric(18,2), cost_per_point_twd
  Numeric(12,6), acquired_at. Consumed FIFO by redeem/transfer_out.
transfer_rules: id, from_program_id, to_program_id, ratio_from,
  ratio_to, bonus_pct Numeric(6,2) DEFAULT 0, min_transfer,
  transfer_days_note, valid_from, valid_until NULL.
  (pingan_wanlitong_rules.json + Marriott transit import here.)
purchase_offers: id, program_id, kind(official|promo|third_party),
  base_price Numeric(18,4), currency, bonus_pct, min/max, effective
  cpp derived, start/end dates, source_note (TripPlus = manual rows).
fx_rates: id, currency, twd_per_unit Numeric(18,6), as_of Date,
  source. UNIQUE(currency, as_of).
award_quotes: id, origin, destination, travel_date, cabin, pax,
  program_id, miles_required, taxes_amount, taxes_currency,
  cash_price_twd NULL, source(seats_aero|manual), created_at.
funding_scenarios (computed, persisted per evaluation run):
  id, award_quote_id FK, method(existing|transfer_chain|purchase|
  cash), path_json Text, true_cost_twd, saving_vs_cash_twd, rank.
award_watches / award_availability: as needed in PW-3.

## Cost engine semantics (the soul)

Given an award_quote: enumerate funding methods —
A existing miles (consume cost lots FIFO → real cost, not market est)
B/C transfer chains up to depth 2 (e.g. 萬里通→FlyingBlue;
  萬里通→Marriott→airline with 60k→25k bonus math), cost = source
  lots consumed or source purchase price
D official/promo purchase offers (currency→TWD via fx_rates)
E third-party manual offers
F cash ticket price.
Output: ranked funding_scenarios with full path explanation. All
deterministic; every number traceable to a lot, rule, offer, or rate.

## Phasing (each phase = one ticket, standard loop)

PW-1 Domain core + data rescue: tables above (through fx_rates);
  legacy import command reading points_wallet.json +
  pingan_wanlitong_rules.json + official_purchase_costs.json →
  accounts/opening lots/transfer_rules/purchase_offers; wallet
  dashboard (per-owner balances, value = lots vs editable valuation,
  expiry list); exchange-rate shared service.
  STOP if the three legacy data files are not provided.
PW-2 Award Cost Engine: award_quotes manual entry, funding_scenarios
  computation A-F, comparison UI. Hand-computed fixture mandatory.
PW-3 seats.aero + Expiry Agent: Partner API search → award_quote
  autofill; watches + snapshots; cron expiry checks (90/60/30/7)
  surfaced on dashboard (notification channel = dashboard first,
  email/LINE later).
PW-4 (reassess before starting) AI layer: LLM reads wallet state +
  calls the engine, explains in prose (Phase 15 call pattern).

## Sequencing vs trading roadmap

PW-1 → PW-2 → PW-3 → Phase 17 → 19 → 18 (user priority ruling
2026-07-06; trading loop delayed ≈ 3-4 weeks — user accepted).
Escape hatch: after PW-2 the wallet already answers "how should I pay
for this ticket" with manual quotes; user may resume trading there.

## Legacy disposition

KEEP as reference/data: server.py cost math, pingan rules JSON,
Marriott transit math, rate fallback, owner/account concepts.
DO NOT PORT: app.js monolith, localStorage persistence, cached cost
fields as truth, TripPlus crawler, old service worker.
