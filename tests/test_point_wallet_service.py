from datetime import date
from decimal import Decimal

import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401
from shared.services.point_wallet_service import (
    add_award_availability,
    add_point_balance,
    add_valuation_rate,
    create_award_watch,
    create_loyalty_program,
    create_transfer_partner,
    get_portfolio_summary,
    list_award_availability,
    list_point_balances,
    list_transfer_partners,
)
from shared.services.seats_aero_service import fetch_award_watch


class MockSeatsAeroClient:
    def cached_search(self, *, origin, destination, cabin, source=None):
        assert origin == "TPE"
        assert destination == "LAX"
        assert cabin == "business"
        return {
            "data": [
                {
                    "date": "2026-10-01",
                    "source": source or "aeroplan",
                    "seats": 2,
                    "mileage": 75000,
                    "taxes": "CAD 88",
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


def test_portfolio_value_uses_latest_balance_and_latest_valuation():
    session = make_session()
    program = create_loyalty_program(session, name="Aeroplan", kind="airline")
    add_point_balance(session, program_id=program.id, balance=Decimal("10000"), as_of=date(2026, 1, 1))
    add_point_balance(session, program_id=program.id, balance=Decimal("12000"), as_of=date(2026, 2, 1))
    add_valuation_rate(session, program_id=program.id, twd_per_point=Decimal("0.300000"), effective_date=date(2026, 1, 1))
    add_valuation_rate(session, program_id=program.id, twd_per_point=Decimal("0.400000"), effective_date=date(2026, 2, 1))

    summary = get_portfolio_summary(session, today=date(2026, 2, 2))

    assert summary["total_value_twd"] == Decimal("4800.00000000")
    assert summary["programs"][0].balance == Decimal("12000.00")
    assert summary["programs"][0].twd_per_point == Decimal("0.400000")


def test_balance_snapshots_are_append_only_and_expiry_filter_uses_90_days():
    session = make_session()
    program = create_loyalty_program(session, name="United", kind="airline")
    add_point_balance(
        session,
        program_id=program.id,
        balance=Decimal("1000"),
        as_of=date(2026, 1, 1),
        expires_at=date(2026, 3, 1),
    )
    add_point_balance(
        session,
        program_id=program.id,
        balance=Decimal("2000"),
        as_of=date(2026, 2, 1),
        expires_at=date(2026, 12, 31),
    )

    summary = get_portfolio_summary(session, today=date(2026, 1, 15))

    assert len(list_point_balances(session)) == 2
    assert summary["programs"][0].balance == Decimal("2000.00")
    assert summary["expiring_soon"] == []


def test_transfer_map_crud_and_manual_availability():
    session = make_session()
    bank = create_loyalty_program(session, name="Bank Points", kind="bank")
    airline = create_loyalty_program(session, name="Aeroplan", kind="airline")
    transfer = create_transfer_partner(
        session,
        from_program_id=bank.id,
        to_program_id=airline.id,
        ratio_from=1,
        ratio_to=1,
        transfer_days="instant",
    )
    watch = create_award_watch(session, origin="tpe", destination="lax", cabin="business", program_id=airline.id)
    availability = add_award_availability(
        session,
        watch_id=watch.id,
        seen_date=date(2026, 7, 6),
        flight_date=date(2026, 10, 1),
        program="Aeroplan",
        seats=2,
        miles_cost=Decimal("75000"),
        taxes_fees="CAD 88",
        source="manual",
    )

    assert list_transfer_partners(session)[0].id == transfer.id
    assert list_award_availability(session)[0].id == availability.id


def test_stage_two_fetch_is_idempotent_with_mocked_http_client():
    session = make_session()
    program = create_loyalty_program(session, name="aeroplan", kind="airline")
    watch = create_award_watch(session, origin="TPE", destination="LAX", cabin="business", program_id=program.id)

    first = fetch_award_watch(session, watch_id=watch.id, client=MockSeatsAeroClient(), seen_date=date(2026, 7, 6))
    second = fetch_award_watch(session, watch_id=watch.id, client=MockSeatsAeroClient(), seen_date=date(2026, 7, 6))

    assert first == {"created": 1}
    assert second == {"created": 0}
    rows = list_award_availability(session)
    assert len(rows) == 1
    assert rows[0].source == "seats_aero"
    assert rows[0].raw is not None
