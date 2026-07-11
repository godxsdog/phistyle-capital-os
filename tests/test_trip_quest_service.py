from datetime import date

import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401
from shared.services.point_wallet_service import create_program
from shared.services.trip_quest_service import pair_availability, run_trip_quest


class MockQuestSeatsClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def cached_search(self, **kwargs):
        self.calls.append((kwargs["origin"], kwargs["destination"]))
        assert kwargs["start_date"] == date(2026, 9, 1)
        assert kwargs["end_date"] == date(2026, 9, 30)
        assert kwargs["source"] is None
        rows = OUTBOUND_RAW if kwargs["origin"] == "TPE" else RETURN_RAW
        return {"data": rows}


OUTBOUND_RAW = [
    {"ID": "o1", "Route": {"OriginAirport": "TPE", "DestinationAirport": "OKA"}, "Date": "2026-09-01", "YAvailable": True, "YMileageCost": "10000", "YRemainingSeats": 2, "Source": "Alaska", "YTaxes": {"Amount": "20", "Currency": "USD"}},
    {"ID": "o2", "Route": {"OriginAirport": "TPE", "DestinationAirport": "OKA"}, "Date": "2026-09-02", "YAvailable": True, "YMileageCost": "8000", "YRemainingSeats": 1, "Source": "Alaska"},
    {"ID": "o3", "Route": {"OriginAirport": "TPE", "DestinationAirport": "OKA"}, "Date": "2026-09-03", "YAvailable": True, "YMileageCost": "12000", "YRemainingSeats": 3, "Source": "Alaska"},
]

RETURN_RAW = [
    {"ID": "r1", "Route": {"OriginAirport": "OKA", "DestinationAirport": "TPE"}, "Date": "2026-09-05", "YAvailable": True, "YMileageCost": "11000", "YRemainingSeats": 2, "Source": "Alaska", "YTaxes": "2500 JPY"},
    {"ID": "r2", "Route": {"OriginAirport": "OKA", "DestinationAirport": "TPE"}, "Date": "2026-09-07", "YAvailable": True, "YMileageCost": "6000", "YRemainingSeats": 3, "Source": "Alaska"},
    {"ID": "r3", "Route": {"OriginAirport": "OKA", "DestinationAirport": "TPE"}, "Date": "2026-09-06", "YAvailable": True, "YMileageCost": "5000", "YRemainingSeats": 3, "Source": "Aeroplan"},
]


def make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_pair_fixture_filters_seats_and_ranks_by_total_miles_then_outbound_date():
    outbound = [
        normalized("o1", "2026-09-01", "10000", 2, "Alaska"),
        normalized("o2", "2026-09-02", "8000", 1, "Alaska"),
        normalized("o3", "2026-09-03", "12000", 3, "Alaska"),
    ]
    returns = [
        normalized("r1", "2026-09-05", "11000", 2, "Alaska"),
        normalized("r2", "2026-09-07", "6000", 3, "Alaska"),
        normalized("r3", "2026-09-06", "5000", 3, "Aeroplan"),
    ]

    pairs = pair_availability(outbound, returns, programs=["Alaska"], trip_days=4, pax=2)

    assert [(pair.outbound_date.isoformat(), pair.return_date.isoformat()) for pair in pairs] == [
        ("2026-09-03", "2026-09-07"),
        ("2026-09-01", "2026-09-05"),
    ]
    assert [str(pair.total_miles) for pair in pairs] == ["18000", "21000"]
    assert all(pair.seats_min >= 2 for pair in pairs)


def test_trip_quest_uses_two_cached_search_calls_and_reuses_same_day_snapshots():
    session = make_session()
    create_program(session, name="Alaska", kind="airline")
    client = MockQuestSeatsClient()
    kwargs = {
        "origin": "TPE",
        "destination": "OKA",
        "programs": ["Alaska"],
        "window_start": date(2026, 9, 1),
        "window_end": date(2026, 9, 30),
        "trip_days": 4,
        "cabin": "economy",
        "pax": 2,
        "run_date": date(2026, 7, 11),
        "client": client,
    }

    first = run_trip_quest(session, **kwargs)
    second = run_trip_quest(session, **kwargs)

    assert client.calls == [("TPE", "OKA"), ("OKA", "TPE")]
    assert first.created_results == 2
    assert second.created_results == 0
    assert [row.id for row in second.results] == [row.id for row in first.results]
    assert first.results[0].rank == 1
    assert first.results[0].total_miles == 18000
    assert first.results[1].outbound_taxes == "20 USD"


def normalized(identifier: str, travel_date: str, miles: str, seats: int, program: str):
    return {
        "seats_aero_id": identifier,
        "travel_date": travel_date,
        "miles_required": miles,
        "remaining_seats": seats,
        "program_source": program,
    }
