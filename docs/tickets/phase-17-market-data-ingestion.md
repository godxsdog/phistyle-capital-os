# Ticket: Phase 17 — Market Data Ingestion v0 (TAIFEX + US daily bars)

FABLE-APPROVED: yes (2026-07-06, written at session close for
continuity; PRE-START REQUIREMENT: run a fresh-context Sonnet clarity
review of this ticket before Codex begins; BLOCKER findings go to a
new Fable session, lower findings may be fixed inline by the review.)
IMPLEMENTATION OWNER: Codex. REVIEW: Sonnet. VERDICT: a new Fable
session with the completion report.
DEPENDS ON: Phase 16 verdict ACCEPTED.

## 1-2. WHY / USER VALUE

Daily-bar store for the backtester (18) and trade-plan mark-to-market
(19). Roadmap §Phase 17.

## 3. STRATEGIC DECISIONS ALREADY MADE

- SOURCES (Fable-decided): (a) TAIFEX official website daily download
  data: TX/MTX/TMF daily OHLCV + open interest, 三大法人 futures
  positions by product, settlement/expiry calendar. Codex verifies the
  exact current download URLs/CSV formats at implementation time;
  needing to scrape beyond documented downloads = STOP.
  (b) US stocks: Stooq free daily CSV (keyless, e.g.
  https://stooq.com/q/d/l/?s=aapl.us&i=d) for watchlist tickers. If
  Stooq is unavailable/unreliable at implementation time → STOP report
  listing alternatives (Alpha Vantage free tier, yfinance) for user
  decision; do NOT silently substitute.
- SCHEDULER (Fable-decided): host-level cron on the Mac mini invoking
  `docker-compose exec backend python -m <ingest command>` once per
  weekday evening; the repo ships the command + a documented crontab
  line (user installs it — that is a deploy-side manual step). The
  in-repo scheduler stub may gain at most a manual-trigger endpoint.
- Ingestion is idempotent per (source, date): re-running upserts
  nothing new, never mutates existing rows (corrections = STOP).
- Data-quality checks: gap detection (missing trading days vs
  calendar), duplicate dates; failures land in an ingest log table,
  never crash the job.

## 5/7. SCOPE + SCHEMA (one migration, revision id ≤ 32 chars)

- watchlist_symbols: id PK; market Text NOT NULL (taifex|us); symbol
  Text NOT NULL; active Boolean NOT NULL DEFAULT true; UNIQUE(market,
  symbol).
- market_daily_bars: id PK; market Text NOT NULL; symbol Text NOT
  NULL; bar_date Date NOT NULL; open/high/low/close Numeric(18,6) NOT
  NULL; volume BigInteger NULL; open_interest BigInteger NULL; source
  Text NOT NULL; UNIQUE(market, symbol, bar_date).
- institutional_positions: id PK; trade_date Date NOT NULL; product
  Text NOT NULL; identity Text NOT NULL (dealer|trust|foreign);
  long_contracts/short_contracts/net_contracts Integer NOT NULL;
  UNIQUE(trade_date, product, identity).
- ingest_runs: id PK; source Text; run_date Date; status Text;
  detail Text NULL; started_at/finished_at timestamptz.
- settlement calendar: store as rows in market_daily_bars? NO —
  separate table settlement_calendar: id PK; product Text; contract
  Text; last_trading_date Date; UNIQUE(product, contract).
  (5 tables total — this ticket's stated migration scope.)
- Endpoints: watchlist CRUD; POST /capital/market-data/ingest (manual
  trigger, per source, idempotent); GET sanity summary (per symbol:
  first/last date, row count, gap count). Minimal frontend page
  showing the sanity table + watchlist management.
- Backfill: TAIFEX ≥ 3 years where downloadable; Stooq full available
  history for watchlist symbols.
- main.py ADDITIVE ONLY. requirements: additions allowed for HTTP
  fetching only if stdlib urllib is insufficient (prefer stdlib).

## 6/8. OUT OF SCOPE / MUST NOT CHANGE

Intraday/tick; options data; realtime; charts; news. Decision
pipeline files, Phase 16 import tables, services/llm_router — no LLM
anywhere in this phase.

## 10-13. RULES / TESTS

No decision-state access. Fixtures: synthetic TAIFEX + Stooq format
samples; gap-detection positive/negative; idempotent re-ingest;
upsert-never-mutate proof. pytest green in .venv (minus failures
proven pre-existing).

## 14. MANUAL VERIFICATION (user)

After deploy+migration: add 台指期+2 US tickers to watchlist, trigger
manual ingest, sanity page shows plausible rows; spot-check one date
against TAIFEX site and one against Stooq; install the crontab line;
confirm next-day auto-ingest ran (ingest_runs row).

## 15. STOP (additional)

Paid source required; format requires scraping; NAS storage pressure;
any temptation to touch decision tables.

## 16. COMPLETION REPORT

Standard format + full migration file pasted.
