from __future__ import annotations

import argparse
import json

from shared.database.session import SessionLocal
from shared.services.route_advisor_service import parse_mileage_guides


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract unconfirmed route sweet spots")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    session = SessionLocal()
    try:
        result = parse_mileage_guides(session, commit=args.commit, progress=lambda message: print(message, flush=True))
        mode = "COMMIT" if args.commit else "DRY-RUN"
        for candidate in result.candidates:
            printable = {
                **candidate,
                "miles_cost": str(candidate["miles_cost"]) if candidate["miles_cost"] is not None else None,
            }
            print(json.dumps(printable, ensure_ascii=False, sort_keys=True))
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        print(
            f"[{mode}] 總結：成功 {result.successful_documents} 檔、"
            f"失敗 {result.failed_documents} 檔、跳過 {result.skipped_documents} 檔、"
            f"候選總數 {len(result.candidates)} 筆",
            flush=True,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
