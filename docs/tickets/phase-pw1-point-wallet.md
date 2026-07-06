# Ticket: Phase PW-1 — Point Wallet Domain Core + Data Rescue

VERDICT: ACCEPTED (Fable, 2026-07-06; commit 83bd112). STATUS:
IMPLEMENTED — VERIFIED after user deploy + migration
0009_pw_domain_core + real import on Mac mini + side-by-side check
vs legacy app.
- Migration reviewed column-for-column vs master spec: APPROVED.
- Fable spot-checks: no rescued data in the commit (verified);
  hash-based idempotent import; unmappable rows → warnings.
- MUST EXAMINE at manual verification: the real dry-run produced
  only 6 cost_lots across 34 accounts and 33 warnings — confirm the
  warning list explains the accounts without cost basis (legacy data
  likely lacks cost fields for most), and that dashboard totals match
  the legacy app. If totals diverge → FIX round, do not accept
  silently.
- Test count thin (8) — same note as Phase 16; backfill
  opportunistically in PW-2.

FABLE-APPROVED: yes (2026-07-06, v2 — supersedes the earlier thin
PW-1 draft after the user's legacy-architecture analysis; the master
spec is docs/strategy/point-wallet-master-spec.md and is BINDING).
IMPLEMENTATION OWNER: Codex. VERDICT: new Fable session.
PREFLIGHT ORDER (mandatory, in this order):
Step 0 — repo identity guard per CLAUDE.md §Session start item 0
  (wrong repo → STOP "WRONG WORKING DIRECTORY").
Step 1 — confirm `data-rescue/` is gitignored (it is, .gitignore:10).
Step 2 — THEN check the prerequisite files below.
HARD PREREQUISITE (STOP without them): the user places the three
legacy data files at repo-root `data-rescue/` (gitignored) IN THE
CANONICAL DEV REPO ON THE MACBOOK:
points_wallet.json, pingan_wanlitong_rules.json,
official_purchase_costs.json. PRIVACY: data-rescue/ is added to
.gitignore in this ticket and its contents are NEVER committed.

## 1-2. WHY / USER VALUE

Rescue the real data (two owners' balances, lot costs, painstakingly
built 平安萬里通 rules) out of the legacy half-app into a clean
domain model, and show the first honest dashboard: what do we hold,
what did each point cost, what expires when.

## 3. STRATEGIC DECISIONS ALREADY MADE

All architecture decisions and the domain model in
point-wallet-master-spec.md §Architecture/§Domain — implement
verbatim; do not redesign. Additional PW-1 specifics:
- Import is an idempotent management command (re-run = no dupes;
  keyed on a stable hash of the source records) that maps: legacy
  accounts → programs+accounts; legacy cached cost fields → ONE
  opening cost_lot per account (labeled source='legacy_import');
  pingan rules → transfer_rules (incl. bonus percentages); official
  purchase costs → purchase_offers. Unmappable fields → import
  warnings listed in the command output, never silently dropped.
- Legacy code in legacy/points-wallet/ is READ for reference; not
  modified, not executed, not ported wholesale.
- Exchange-rate shared service: shared/services/
  exchange_rate_service.py — fetch open.er-api.com, persist to
  fx_rates, static fallback table when API fails (port the legacy
  fallback values), used by the dashboard for any non-TWD costs.
- Dashboard value display: per account show BOTH lot-based real cost
  and current market-style valuation IF the user enters one
  (valuation entry optional in PW-1; lots are the truth).

## 5/7. SCOPE

One additive migration (id ≤ 32 chars): programs, accounts,
ledger_transactions, cost_lots, transfer_rules, purchase_offers,
fx_rates — columns exactly per master spec §Domain model.
Services: point_wallet_service.py, legacy_import command,
exchange_rate_service.py. Routes additive in main.py: CRUD
(programs/accounts/transactions incl. manual lot adjustments,
transfer_rules, purchase_offers), portfolio summary (per owner:
balances, lot cost totals, expiry ≤90d), fx refresh trigger.
Frontend: /wallet dashboard (owner tabs, per-program table: balance /
real cost basis / expiry), balances+ledger entry forms, transfer
rules table, offers table. Nav link. Tests: import round-trip on a
SYNTHETIC fixture mimicking the three files' shapes (real files never
enter tests), lot math hand-computed, append-only ledger, fx fallback,
idempotent re-import.

## 6/8. OUT OF SCOPE / MUST NOT CHANGE

Award cost engine (PW-2); seats.aero (PW-3); notifications; LLM;
auth; TripPlus crawling; decision pipeline, trading tables,
llm_router, existing migrations, legacy/ directory contents.

## 9-15. RULES / STOPS

Standard invariants. Ledger append-only; lots consumed FIFO only by
future redeem/transfer flows (PW-2) — PW-1 only creates/imports lots.
STOP: missing data-rescue files; legacy JSON shape materially differs
from the synthetic fixture assumptions (report actual shape, wait);
any credential-like field found in legacy data (mask, warn, never
store raw); schema beyond spec.

## 14. MANUAL VERIFICATION (user)

After deploy+migration: run import against the real rescued files on
the Mac mini; dashboard totals match the legacy app side-by-side
(balances exact, cost totals within rounding); expiry list sane;
re-run import → no duplicates.

## 16. COMPLETION REPORT

Standard + migration pasted + import warning list from a synthetic
dry-run.
