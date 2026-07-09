# Ticket: Phase 17 — Market Data Ingestion v0 (TAIFEX + US daily bars)

FABLE-APPROVED: yes (2026-07-06).
VERDICT: ACCEPTED + VERIFIED (Fable, 2026-07-09). Implemented by
Sonnet (Codex out of tokens; commits 7d817d3 + e80ea47 test fix +
Dockerfile tools/ fix after a deploy crash — lesson: new top-level
dirs imported by backend MUST be added to backend/Dockerfile COPY).
Deployed, migrations 0012/0013 applied, user verified live.
Current phase → 19.
PRE-START SONNET REVIEW: COMPLETED 2026-07-08 (fresh-context Sonnet,
run by Fable). Findings: 1 BLOCKER + 2 HIGH + 2 MEDIUM, all fixed in
this ticket (runtime correction semantics, ingest_runs/
settlement_calendar nullability, contract YYYYMM, TAIFEX not
watchlist-gated). Codex may start.
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
  (b) US stocks — SOURCE CHANGED BY FABLE 2026-07-08(Stooq 已被
  Cloudflare JS 驗證擋死,Codex STOP 正確):改用 Yahoo Finance
  公開 chart JSON 端點(keyless、stdlib urllib + 瀏覽器 User-Agent
  header):
  https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?range=10y&interval=1d
  解析 timestamp/open/high/low/close/volume,另存 adjclose 於
  close 欄?否——bars 存原始 OHLCV,adjclose 存入 open_interest
  以外的方式不允許:v0 只存原始 close,並在資料健康頁註明
  「未復權,除權息日會有跳空」(known limitation,回測 v0 接受)。
  屬非官方端點:失敗即 fail loud 進 ingest_runs,不重試爬蟲。
  此源也不可用時 → STOP 列 Alpha Vantage(需 key、25次/日)
  供使用者決定。
- SCHEDULER (Fable-decided): host-level cron on the Mac mini invoking
  `docker-compose exec backend python -m <ingest command>` once per
  weekday evening; the repo ships the command + a documented crontab
  line (user installs it — that is a deploy-side manual step). The
  in-repo scheduler stub may gain at most a manual-trigger endpoint.
- Ingestion is idempotent per (source, date): re-running upserts
  nothing new, never mutates existing rows. RUNTIME correction
  handling(這是執行期行為,不是實作期 STOP):若重抓值與既有列
  不同,不覆寫,寫入一筆 ingest_runs status='correction_detected'
  + detail(symbol/date/舊值/新值),繼續處理其餘列;
  correction 顯示在資料健康頁供人工裁決。
- TAIFEX 的 TX/MTX/TMF 為固定內建商品,不經 watchlist 閘控;
  watchlist_symbols 只閘控美股標的。
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
- ingest_runs: id PK; source Text NOT NULL; run_date Date NOT NULL;
  status Text NOT NULL; detail Text NULL; started_at timestamptz
  NOT NULL; finished_at timestamptz NULL.
- settlement calendar: store as rows in market_daily_bars? NO —
  separate table settlement_calendar: id PK; product Text NOT NULL;
  contract Text NOT NULL(合約月份碼,格式 YYYYMM);
  last_trading_date Date NOT NULL; UNIQUE(product, contract).
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

After deploy+migration: add 2 US tickers to watchlist (TAIFEX 內建
不需加), trigger
manual ingest, sanity page shows plausible rows; spot-check one date
against TAIFEX site and one against Stooq; install the crontab line;
confirm next-day auto-ingest ran (ingest_runs row).

## 15. STOP (additional)

Paid source required; format requires scraping; NAS storage pressure;
any temptation to touch decision tables.

## 16. COMPLETION REPORT

Standard format + full migration file pasted.
