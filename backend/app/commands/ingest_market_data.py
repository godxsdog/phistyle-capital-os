from __future__ import annotations

import argparse
from datetime import date, timedelta

from shared.database.session import SessionLocal
from shared.services.market_data_service import ingest_taifex, ingest_yahoo_us


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Phase 17 market data.")
    parser.add_argument("--source", choices=["taifex", "yahoo", "all"], default="all")
    parser.add_argument("--start-date", help="YYYY-MM-DD; TAIFEX only. Defaults to 3 years ago.")
    parser.add_argument("--end-date", help="YYYY-MM-DD; defaults to today.")
    args = parser.parse_args()

    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = date.fromisoformat(args.start_date) if args.start_date else end_date - timedelta(days=365 * 3 + 7)

    with SessionLocal() as session:
        if args.source in {"taifex", "all"}:
            result = ingest_taifex(session, start_date=start_date, end_date=end_date)
            print(f"TAIFEX {result.status}: inserted={result.inserted} skipped={result.skipped} warnings={len(result.warnings)}")
        if args.source in {"yahoo", "all"}:
            result = ingest_yahoo_us(session)
            print(f"Yahoo {result.status}: inserted={result.inserted} skipped={result.skipped} warnings={len(result.warnings)}")


if __name__ == "__main__":
    main()
