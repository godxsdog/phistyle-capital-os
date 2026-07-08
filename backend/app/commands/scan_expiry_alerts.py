from __future__ import annotations

from datetime import date

from shared.database.session import SessionLocal
from shared.services.seats_aero_service import scan_expiry_alerts


def main() -> None:
    session = SessionLocal()
    try:
        alerts = scan_expiry_alerts(session, today=date.today())
        print(f"expiry scan complete: alerts_created={len(alerts)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
