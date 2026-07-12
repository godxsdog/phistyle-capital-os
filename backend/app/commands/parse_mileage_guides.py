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
        result = parse_mileage_guides(session, commit=args.commit)
        mode = "COMMIT" if args.commit else "DRY-RUN"
        print(
            f"[{mode}] sweet spots: candidates={len(result.candidates)} "
            f"created={len(result.created)} skipped_documents={result.skipped_documents}"
        )
        for candidate in result.candidates:
            printable = {
                **candidate,
                "miles_cost": str(candidate["miles_cost"]) if candidate["miles_cost"] is not None else None,
            }
            print(json.dumps(printable, ensure_ascii=False, sort_keys=True))
        for warning in result.warnings:
            print(f"WARNING: {warning}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
