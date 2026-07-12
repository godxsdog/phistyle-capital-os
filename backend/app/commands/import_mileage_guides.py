from __future__ import annotations

import argparse
from pathlib import Path

from shared.database.session import SessionLocal
from shared.services.route_advisor_service import import_mileage_guides


def main() -> None:
    parser = argparse.ArgumentParser(description="Import mileage guide text files")
    parser.add_argument("--guide-dir", type=Path, default=Path("data-rescue/guides"))
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    if not args.guide_dir.is_dir():
        raise SystemExit(f"guide directory not found: {args.guide_dir}")
    session = SessionLocal()
    try:
        result = import_mileage_guides(session, guide_dir=args.guide_dir, commit=args.commit)
        mode = "COMMIT" if args.commit else "DRY-RUN"
        print(f"[{mode}] mileage guides: candidates={len(result.candidates)} skipped={result.skipped}")
        for candidate in result.candidates:
            print(f"- {candidate.title} | {candidate.filename} | sha256:{candidate.sha256}")
        print(f"created={len(result.created)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
