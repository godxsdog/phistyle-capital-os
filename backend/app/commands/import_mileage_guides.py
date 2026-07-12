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
        print(
            f"[{mode}] 掃到 {result.scanned} 檔、候選 {len(result.candidates)}、"
            f"匯入 {len(result.created)}、跳過 {len(result.skipped)}"
        )
        for candidate in result.candidates:
            action = "將匯入" if not args.commit else "已匯入"
            print(f"{action}: {candidate.filename} | title={candidate.title} | sha256:{candidate.sha256}")
        for skipped in result.skipped:
            print(f"跳過: {skipped.filename} | 原因={skipped.reason}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
