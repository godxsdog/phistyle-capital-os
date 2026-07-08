from datetime import date
from decimal import Decimal

import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401
from shared.services.point_wallet_service import create_account, create_ledger_transaction, create_program
from shared.services.seats_aero_service import (
    create_award_watch,
    fetch_award_watch,
    list_expiry_alerts,
    promote_snapshot_to_award_quote,
    scan_expiry_alerts,
)


class MockSeatsClient:
    def __init__(self) -> None:
        self.calls = 0

    def cached_search(self, **kwargs):
        self.calls += 1
        assert kwargs["origin"] == "TPE"
        assert kwargs["destination"] == "TYO"
        assert kwargs["cabin"] == "business"
        return {
            "data": [
                {
                    "ID": "avail-1",
                    "Route": {"OriginAirport": "TPE", "DestinationAirport": "TYO", "Source": "aeroplan"},
                    "Date": "2026-11-01",
                    "JAvailable": True,
                    "JMileageCost": "45000",
                    "JRemainingSeats": 2,
                    "JAirlines": "BR",
                    "JDirect": True,
                    "Source": "aeroplan",
                    "UpdatedAt": "2026-07-08T00:00:00Z",
                }
            ]
        }


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_seats_aero_snapshot_is_idempotent_and_promotes_to_award_quote():
    session = make_session()
    aeroplan = create_program(session, name="aeroplan", kind="airline")
    watch = create_award_watch(
        session,
        origin="tpe",
        destination="tyo",
        cabin="business",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 7),
        program_id=aeroplan.id,
    )
    client = MockSeatsClient()

    first = fetch_award_watch(session, watch_id=watch.id, client=client, seen_date=date(2026, 7, 8))
    second = fetch_award_watch(session, watch_id=watch.id, client=client, seen_date=date(2026, 7, 8))
    quote = promote_snapshot_to_award_quote(session, snapshot_id=first.snapshot.id)

    assert first.created is True
    assert second.created is False
    assert first.snapshot.id == second.snapshot.id
    assert client.calls == 1
    assert first.snapshot.result_count == 1
    assert quote.source == "seats_aero"
    assert quote.program_id == aeroplan.id
    assert quote.origin == "TPE"
    assert quote.destination == "TYO"
    assert quote.travel_date == date(2026, 11, 1)
    assert quote.cabin == "business"
    assert quote.miles_required == Decimal("45000")


def test_expiry_scan_creates_threshold_alerts_idempotently():
    session = make_session()
    program = create_program(session, name="Qatar Avios", kind="airline")
    account = create_account(session, owner="kent", program_id=program.id)
    create_ledger_transaction(
        session,
        account_id=account.id,
        kind="earn",
        quantity=Decimal("12000"),
        occurred_at=date(2026, 1, 1),
        note="legacy import expires_at=2026-10-06",
        create_lot=False,
    )

    first = scan_expiry_alerts(session, today=date(2026, 7, 8))
    second = scan_expiry_alerts(session, today=date(2026, 7, 8))

    alerts = list_expiry_alerts(session)
    assert len(first) == 1
    assert second == []
    assert len(alerts) == 1
    assert alerts[0].threshold_days == 90
    assert alerts[0].balance == Decimal("12000.00")
    assert "Qatar Avios" in alerts[0].message
