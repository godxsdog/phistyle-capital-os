# Phase 17 Market Data Ingestion

PhiStyle Capital OS v0 stores daily bars for TAIFEX futures and US watchlist symbols. The store is read-only input for later backtesting and trade-plan mark-to-market phases; it does not touch the decision pipeline and never places orders.

## Sources

- TAIFEX daily futures bars: official `futDataDown` download endpoint for TX, MTX, and TMF. The response is MS950/Big5 CSV and includes OHLC, volume, open interest, contract month, and trading session.
- TAIFEX institutional positions: official `futContractsDate` form endpoint for TXF, MXF, and TMF. The parser reads the official HTML table and stores dealer, trust, and foreign open-interest long/short/net contracts.
- TAIFEX settlement calendar v0: derived from official TAIFEX daily futures download contract months by storing the latest observed trading date per product/contract. This is conservative and append-only; future phases may replace it with a richer official calendar feed if TAIFEX exposes one cleanly.
- US daily bars: Yahoo Finance v8 chart JSON endpoint, keyless, with a browser User-Agent header:
  `https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?range=10y&interval=1d`

US bars store raw OHLCV only. Adjusted close is intentionally not stored in v0, so US data health and UI note: `未復權，除權息日會有跳空`.

## Idempotency

Market bars are unique per `(market, symbol, bar_date)`. Re-ingest inserts missing rows only and never mutates existing bars. If a fetched row differs from an existing row, the existing row is preserved and an `ingest_runs` row with `status='correction_detected'` records the old/new values for manual review.

Quality checks record warnings in `ingest_runs` and do not crash the job.

## Manual Commands

Run the migration on Mac mini only after Fable verifies the migration file:

```bash
cd ~/Server/phistyle-capital-os
/usr/local/bin/docker-compose exec backend python -m alembic -c /app/alembic.ini upgrade 0012_market_data
```

Manual ingest:

```bash
cd ~/Server/phistyle-capital-os
/usr/local/bin/docker-compose exec backend python -m backend.app.commands.ingest_market_data --source all
```

TAIFEX backfill with explicit range:

```bash
/usr/local/bin/docker-compose exec backend python -m backend.app.commands.ingest_market_data --source taifex --start-date 2023-07-01 --end-date 2026-07-09
```

## Cron

Install on the Mac mini host with Asia/Taipei local time. Suggested weekday evening line:

```cron
30 18 * * 1-5 cd /Users/kaichanghuang/Server/phistyle-capital-os && /usr/local/bin/docker-compose exec -T backend python -m backend.app.commands.ingest_market_data --source all >> /tmp/phistyle_market_ingest.log 2>&1
```

The user installs cron manually. The repository does not auto-deploy or auto-schedule jobs.
