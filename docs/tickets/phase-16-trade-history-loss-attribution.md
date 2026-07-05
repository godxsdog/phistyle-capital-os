# Ticket: Phase 16 — Trade History Import & Loss Attribution

FABLE-APPROVED: yes (2026-07-06)
SCOPE NOTE: Schwab parser + analytics NOW; KGI futures parser is a
declared follow-up round of THIS phase once the user provides a KGI
sample (STOP: never guess the KGI format).
IMPLEMENTATION OWNER: Codex. REVIEW: Sonnet. VERDICT: Fable.

## 1. WHY THIS PHASE EXISTS

The user traded futures and stocks with net losses. Before building
strategy tooling, make past trading legible. See
docs/strategy/current-roadmap.md §Phase 16.

## 2. USER VALUE

Upload broker statements → a Loss Attribution dashboard: realized P&L
by symbol, direction, holding period, instrument class (leveraged ETF
vs common stock vs futures), entry weekday/hour buckets,
averaging-down detection, win rate / expectancy / max consecutive
losses, plus one LLM-written narrative (Phase 15 pattern) the user can
challenge.

## 3. STRATEGIC DECISIONS ALREADY MADE (do not reopen)

- PRIVACY (hard rule): real broker files are NEVER committed to the
  repo (it has a GitHub remote). Tests use synthetic fixtures that
  mimic the format. Uploaded files are parsed from the request body in
  memory; the content hash is computed in memory; the raw file is never
  written to disk, BLOB column, or logs.
- Parser v0 target: Schwab account statement CSV, UTF-8 with BOM,
  Chinese-locale headers, multi-section. Verified structure from the
  user's real sample (2026-07-06):
  - Sections are introduced by literal header lines: 現金餘額 /
    期貨概覽 / 外匯概覽 / 加密貨幣…賬戶概覽 / 賬戶訂單歷史 /
    賬戶交易歷史 / 股票 / 盈虧.
  - PRIMARY DATA = section 賬戶交易歷史, columns:
    (empty),執行時間,價差,市場方,數量,倉位影響,代號,到期日,行使價,類型,價格,淨價,訂單類型
    · 執行時間 format M/D/YY HH:MM:SS (broker-local; store raw string
      AND parsed naive datetime; do not invent a timezone)
    · 市場方 ∈ {買入, 賣出}; 數量 signed like +100/-62;
      倉位影響 ∈ {開倉, 平倉}; 類型 e.g. 股票/ETF
  - SECONDARY DATA = section 現金餘額 rows with 類型=TRD, columns:
    日期,時間,類型,參考號,說明,雜項費用,佣金及費用,數額,餘額 —
    參考號 looks like ="1006551829111" (strip ="…" wrapper);
    說明 like "BOT +200 UUUU @19.385"; money fields use quoted
    thousands separators and may be negative.
  - HEADER GOTCHA: header cells contain zero-width characters
    (U+200B) — the parser MUST strip ​ and BOM before matching.
  - Duplicate-looking fill rows exist legitimately (partial fills,
    same ref#): do NOT dedupe on (time,symbol,qty,price); dedupe only
    whole-file re-imports via a content hash per import batch.
- Realized-trade construction (COMPLETE spec, no interpretation):
  1. Sort fills by parsed executed_at ascending; ties keep file order
     (stable sort).
  2. Per symbol, 開倉 fills append lots (FIFO queue per direction);
     平倉 fills consume lots oldest-first.
  3. Each 平倉 fill produces exactly ONE realized_trades row: quantity
     = consumed quantity, avg_entry = quantity-weighted average of the
     consumed lots, avg_exit = that fill's price, opened_at = earliest
     consumed lot's time, closed_at = fill time.
  4. If a 平倉 fill's quantity exceeds open lots, consume what exists
     and record the EXCESS as a per-row import warning ("unmatched
     closing quantity") — never auto-create an opposite position.
     Position flips are therefore never inferred; if the data implies
     one, it surfaces as warnings, not invented trades.
  5. Quantities are stored ABSOLUTE with a separate side field; signs
     in the CSV are parsed then normalized.
  Shorts (賣出+開倉) use the same logic inverted. Two-digit years
  parse as 20YY; dates are M/D/YY (verified against the sample's
  statement-period header 6/1/26至7/5/26). One file = one account
  (assumption; evidence of multiple accounts in one file = STOP).
  Currency: USD for Schwab; every table carries currency (TWD arrives
  with KGI).
- Fees v0: aggregate 雜項費用+佣金及費用 from cash TRD rows per
  symbol+month and report them alongside gross FIFO P&L. Exact
  per-fill fee allocation is OUT of v0 (documented limitation).
- Leveraged-instrument flag: a hardcoded, easily-editable set seeded
  with {TSLL, TSMX, NVDX, TQQQ, SQQQ} + a "2X/3X/Bull/Bear/UltraPro"
  name heuristic on the description where available.
- Averaging-down detection: within one open position, ≥2 additional
  開倉 fills at successively lower prices (long) / higher (short).
- LLM narrative: lives in shared/services/trade_attribution_service.py
  and calls DeepSeekProvider DIRECTLY (same call pattern as Phase 15:
  strict JSON, validation, fallback, llm_backed metadata) — do NOT
  import, call, or modify BrainOrchestrator/runtime.py. The LLM never
  computes numbers, only narrates the deterministic metrics it is
  given. Metrics are computed on read — NO cache table (the migration
  is fixed at four tables). Storage note (Phase 15 lesson):
  any LLM free-text field must be stored in a Text column with no
  format constraints (no comma-joined lists).

## 4. CURRENT VERIFIED CONTRACTS

Phase 14 terminal-state guards and Phase 15 BrainReview behavior are
live (see those tickets). This phase touches NEITHER. The decision
pipeline is not involved — this is a new, parallel vertical slice
(import → analytics → dashboard).

## 5. IN SCOPE

- Migration (additive; revision id ≤ 32 chars): import_batches
  (id, source=schwab|kgi, content_hash unique, imported_at, row
  counts), trade_fills (batch FK, executed_at raw+parsed, symbol,
  side, quantity, position_effect, instrument_type, price, net_price,
  order_type, currency), cash_transactions (batch FK, date, time,
  ref_no, description, misc_fees, commissions_fees, amount, currency),
  realized_trades (symbol, direction, opened_at, closed_at, quantity,
  avg_entry, avg_exit, gross_pnl, currency, holding_period_seconds,
  batch scope) — realized_trades are derived and rebuilt per import.
- POST /capital/trade-imports (multipart CSV upload, source=schwab) →
  parse, validate, persist, rebuild realized trades; idempotent by
  content hash (re-upload same file = no-op, reported as such).
- GET endpoints for batches, fills, realized trades, and computed
  attribution metrics (metrics computed on read or cached — Codex's
  choice, must be deterministic).
- Frontend: /capital/history page — upload control, import status,
  attribution dashboard (tables are fine; no charting library in v0),
  LLM narrative block with llm_backed indicator.
- Synthetic fixture files exercising: BOM+ZWSP headers, quoted
  thousands separators, ="ref" wrappers, partial-fill duplicates,
  shorts, multi-section skipping (訂單歷史 section is IGNORED in v0 —
  cancelled orders are not trades).
- Janitorial: diagnose the 9 pre-existing router/provider test
  failures under the 3.12 venv; report root cause in the completion
  report; fix ONLY if the fix touches tests alone (any product-code
  fix → report, do not do).

## 6. OUT OF SCOPE

KGI parsing (follow-up round of this phase); broker APIs; automatic
sync; market data; backtesting; per-fill fee allocation; options
(到期日/行使價 columns are parsed but option rows may be rejected with
a clear per-row import warning in v0); the decision pipeline; charts.

## 7. EXPECTED FILES / LAYERS TO CHANGE

New: shared/models/trade_history.py, shared/services/
trade_import_service.py + trade_attribution_service.py, one migration,
frontend/app/capital/history/*, tests. Modified: backend/app/main.py
(ADDITIVE ONLY — new imports + new routes; zero changes to existing
handlers), backend/requirements.txt (add python-multipart, required by
FastAPI for UploadFile), frontend/lib/capitalApi.ts (types+calls),
frontend navigation link if one exists.

Migration column specs (authoritative; Numeric = sa.Numeric):
- import_batches: id PK; source Text NOT NULL; content_hash Text NOT
  NULL UNIQUE; imported_at timestamptz server_default now(); fill_count
  Integer NOT NULL DEFAULT 0; cash_row_count Integer NOT NULL DEFAULT
  0; warning_count Integer NOT NULL DEFAULT 0; warnings Text NULL
  (JSON-encoded list).
- trade_fills: id PK; import_batch_id FK→import_batches.id ondelete
  CASCADE NOT NULL; executed_at_raw Text NOT NULL; executed_at
  DateTime NULL; symbol Text NOT NULL; side Text NOT NULL (buy|sell);
  quantity Numeric(18,4) NOT NULL (absolute); position_effect Text NOT
  NULL (open|close); instrument_type Text NULL; price Numeric(18,6)
  NOT NULL; net_price Numeric(18,6) NULL; order_type Text NULL;
  currency Text NOT NULL DEFAULT 'USD'.
- cash_transactions: id PK; import_batch_id FK CASCADE NOT NULL;
  txn_date Date NOT NULL; txn_time Text NULL; ref_no Text NULL;
  description Text NOT NULL; misc_fees Numeric(18,2) NULL;
  commissions_fees Numeric(18,2) NULL; amount Numeric(18,2) NULL;
  currency Text NOT NULL DEFAULT 'USD'.
- realized_trades: id PK; import_batch_id FK CASCADE NOT NULL; symbol
  Text NOT NULL; direction Text NOT NULL (long|short); opened_at
  DateTime NULL; closed_at DateTime NULL; quantity Numeric(18,4) NOT
  NULL; avg_entry Numeric(18,6) NOT NULL; avg_exit Numeric(18,6) NOT
  NULL; gross_pnl Numeric(18,2) NOT NULL; currency Text NOT NULL;
  holding_period_seconds BigInteger NULL.

## 8. FILES / LAYERS THAT MUST NOT CHANGE

Everything in the decision pipeline: decision_request/brain_review/
human_review/decision-log models & services, BrainOrchestrator,
TriageAgent, capital_decision_support_service, services/llm_router/*
(consume providers as-is), existing migrations, scripts/*, existing
tests.

## 9. DATA / MIGRATION EXPECTATION

EXPECTED: exactly one additive migration creating the four new tables
above. Revision id ≤ 32 characters. Anything touching existing tables
= STOP.

## 10. STATE-TRANSITION RULES

None. This phase must not read or write DecisionRequest/DecisionLog/
HumanReview state.

## 11. IDEMPOTENCY REQUIREMENTS

Re-uploading an identical file (content hash) creates nothing and says
so. Rebuilding realized_trades for a batch is deterministic —
re-import + rebuild yields identical rows.

## 12. ERROR HANDLING

Malformed rows: import continues, per-row warnings are collected and
returned + stored on the batch (never silently dropped). Unparseable
file/section: import fails atomically with a clear error; no partial
batch persists. LLM narrative failure → dashboard shows metrics with
"narrative unavailable" fallback (never blocks the page).

## 13. ACCEPTANCE TESTS

Parser: fixture round-trips all §5 quirks (BOM, ZWSP, ="ref",
thousands separators, partial fills, shorts, section skipping).
FIFO: hand-computed fixture with opens/partial closes/short cycle →
exact realized trades and gross P&L (in tests, not floating guesses).
Idempotency: double upload → single batch. Metrics: averaging-down
detector positive and negative cases; leveraged flag cases.
API: upload → 200 with counts; warnings surfaced. LLM narrative:
mocked provider, fallback case. Full suite green in .venv except the
9 known failures (or fewer, if the janitorial diagnosis fixes them).

## 14. MANUAL VERIFICATION (user)

After deploy + migration: upload the real Schwab statement in the
browser; confirm batch imported with row counts matching the file,
realized trades look sane against the 盈虧 section (e.g. TSLL YTD
≈ −$2,696 gross-of-fees for the covered period), narrative renders
with llm_backed=true.

## 15. STOP CONDITIONS (additional)

Any KGI work without a sample file; any need to modify decision-
pipeline files; options rows requiring schema changes; ambiguity in
FIFO semantics not settled here (report with a concrete example).

## 16. COMPLETION REPORT FORMAT

Standard format, including the full migration file pasted for Fable
review before the user runs it.
