from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.database.session import SessionLocal
from shared.services.point_wallet_legacy_import import import_legacy_point_wallet_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Import rescued legacy Point Wallet data.")
    parser.add_argument("--data-dir", default="data-rescue", help="Directory containing the three rescued JSON files.")
    args = parser.parse_args()
    session = SessionLocal()
    try:
        result = import_legacy_point_wallet_data(session, data_dir=Path(args.data_dir))
        print(json.dumps({"created": result.created, "warnings": result.warnings}, ensure_ascii=False, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
