import json
from datetime import date

import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401
from shared.models.point_wallet import AwardWatch
from shared.services.point_wallet_service import create_program
from shared.services.seats_aero_service import SeatsAeroError
from shared.services.trip_quest_service import run_chain_quest


def raw(identifier, origin, destination, travel_date, miles, seats):
    return {
        "ID": identifier,
        "Date": travel_date,
        "Route": {"OriginAirport": origin, "DestinationAirport": destination},
        "Source": "united",
        "JAvailable": True,
        "JMileageCost": str(miles),
        "JRemainingSeats": seats,
        "JTotalTaxes": 3560,
        "TaxesCurrency": "USD",
    }


class MockChainSeatsClient:
    def __init__(self):
        self.cached_calls = []
        self.trip_calls = []

    def cached_search(self, **kwargs):
        route = (kwargs["origin"], kwargs["destination"])
        self.cached_calls.append(route)
        return {"data": SEGMENT_ONE if route == ("TPE", "SIN") else SEGMENT_TWO}

    def get_trips(self, *, availability_id, include_filtered=True):
        self.trip_calls.append(availability_id)
        if availability_id == "s2-d5":
            raise SeatsAeroError("synthetic detail outage")
        if availability_id == "s1-d4":
            return {"data": [
                {
                    "ID": "economy-two-seats",
                    "Cabin": "economy",
                    "MileageCost": 7500,
                    "RemainingSeats": 2,
                    "TotalTaxes": 3560,
                    "TaxesCurrency": "USD",
                },
                {
                    "ID": "business-zero-seats",
                    "Cabin": "business",
                    "MileageCost": 22000,
                    "RemainingSeats": 0,
                    "TotalTaxes": 3560,
                    "TaxesCurrency": "USD",
                },
            ]}
        detail = {
            "s1-d1": (16000, 2), "s2-d1": (12000, 2),
            "s2-d4": (9000, 2),
            "s1-d5": (25000, 2),
        }[availability_id]
        return {"data": [{
            "ID": f"trip-{availability_id}",
            "Cabin": "business",
            "MileageCost": detail[0],
            "RemainingSeats": detail[1],
            "TotalTaxes": 3560,
            "TaxesCurrency": "USD",
        }]}


SEGMENT_ONE = [
    raw("s1-d1", "TPE", "SIN", "2026-11-01", 20000, 2),
    raw("s1-d2", "TPE", "SIN", "2026-11-02", 18000, 2),
    raw("s1-d3", "TPE", "SIN", "2026-11-03", 15000, 1),
    raw("s1-d4", "TPE", "SIN", "2026-11-04", 22000, 2),
    raw("s1-d5", "TPE", "SIN", "2026-11-05", 25000, 2),
]

SEGMENT_TWO = [
    raw("s2-d1", "SIN", "MLE", "2026-11-01", 12000, 2),
    raw("s2-d3", "SIN", "MLE", "2026-11-03", 10000, 2),
    raw("s2-d4", "SIN", "MLE", "2026-11-04", 8000, 2),
    raw("s2-d5", "SIN", "MLE", "2026-11-05", 10000, 2),
]


def test_chain_requires_all_segments_same_day_filters_seats_and_ranks_verified_first():
    session = make_session()
    create_program(session, name="United", kind="airline")
    client = MockChainSeatsClient()
    kwargs = {
        "segments": [{"origin": "TPE", "destination": "SIN"}, {"origin": "SIN", "destination": "MLE"}],
        "programs": ["United"],
        "window_start": date(2026, 11, 1),
        "window_end": date(2026, 11, 5),
        "cabin": "business",
        "pax": 2,
        "run_date": date(2026, 7, 12),
        "client": client,
    }

    first = run_chain_quest(session, **kwargs)
    second = run_chain_quest(session, **kwargs)

    assert [row.outbound_date.isoformat() for row in first.results] == ["2026-11-01", "2026-11-05"]
    assert [str(row.total_miles) for row in first.results] == ["28000", "35000"]
    assert [json.loads(row.raw_refs)["bucket_verified"] for row in first.results] == [True, False]
    assert "2026-11-02" not in {row.outbound_date.isoformat() for row in first.results}
    assert "2026-11-03" not in {row.outbound_date.isoformat() for row in first.results}
    assert "2026-11-04" not in {row.outbound_date.isoformat() for row in first.results}
    assert json.loads(first.results[0].segments_json)[0]["taxes"] == "35.60 USD"
    assert second.created_results == 0
    assert client.cached_calls == [("TPE", "SIN"), ("SIN", "MLE")]
    assert client.trip_calls == ["s1-d4", "s1-d1", "s2-d1", "s1-d5", "s2-d5"]
    detail_notes = list(session.scalars(select(AwardWatch.note).where(AwardWatch.note.like("seats_trip_detail:%"))))
    assert detail_notes
    assert all(note.startswith("seats_trip_detail:business:") for note in detail_notes)


def make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
