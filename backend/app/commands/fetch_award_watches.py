from __future__ import annotations

from datetime import date

from shared.database.session import SessionLocal
from shared.services.seats_aero_service import fetch_active_award_watches


def main() -> None:
    session = SessionLocal()
    try:
        results = fetch_active_award_watches(session, seen_date=date.today())
        created = sum(1 for result in results if result.created)
        print(f"award watch fetch complete: watches={len(results)} snapshots_created={created}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
