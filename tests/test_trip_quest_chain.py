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
                    "DepartsAt": "2026-11-04T08:00:00Z",
                    "ArrivesAt": "2026-11-04T11:00:00Z",
                },
                {
                    "ID": "business-zero-seats",
                    "Cabin": "business",
                    "MileageCost": 22000,
                    "RemainingSeats": 0,
                    "TotalTaxes": 3560,
                    "TaxesCurrency": "USD",
                    "DepartsAt": "2026-11-04T08:00:00Z",
                    "ArrivesAt": "2026-11-04T11:00:00Z",
                },
            ]}
        if availability_id == "s1-d1":
            return {"data": [
                detail_row("s1-d1-too-late", 14000, "2026-11-01T09:00:00Z", "2026-11-01T15:00:00Z"),
                detail_row("s1-d1-connects", 16000, "2026-11-01T07:00:00Z", "2026-11-01T11:00:00Z"),
            ]}
        details = {
            "s2-d1": (12000, "2026-11-01T14:00:00Z", "2026-11-01T18:00:00Z"),
            "s1-d2": (18000, "2026-11-02T08:00:00Z", "2026-11-02T12:00:00Z"),
            "s2-d2": (10000, "2026-11-02T14:00:00Z", "2026-11-02T18:00:00Z"),
            "s1-d3": (15000, "2026-11-03T08:00:00Z", "2026-11-03T15:00:00Z"),
            "s2-d3": (10000, "2026-11-03T14:00:00Z", "2026-11-03T18:00:00Z"),
            "s1-d5": (25000, "2026-11-05T08:00:00Z", "2026-11-05T11:00:00Z"),
        }[availability_id]
        return {"data": [detail_row(f"trip-{availability_id}", *details)]}


def detail_row(identifier, miles, departs_at, arrives_at):
    return {
        "ID": identifier,
        "Cabin": "business",
        "MileageCost": miles,
        "RemainingSeats": 2,
        "TotalTaxes": 3560,
        "TaxesCurrency": "USD",
        "DepartsAt": departs_at,
        "ArrivesAt": arrives_at,
        "FlightNumbers": identifier,
    }


SEGMENT_ONE = [
    raw("s1-d1", "TPE", "SIN", "2026-11-01", 20000, 2),
    raw("s1-d2", "TPE", "SIN", "2026-11-02", 18000, 2),
    raw("s1-d3", "TPE", "SIN", "2026-11-03", 15000, 2),
    raw("s1-d4", "TPE", "SIN", "2026-11-04", 22000, 2),
    raw("s1-d5", "TPE", "SIN", "2026-11-05", 25000, 2),
]

SEGMENT_TWO = [
    raw("s2-d1", "SIN", "MLE", "2026-11-01", 12000, 2),
    raw("s2-d2", "SIN", "MLE", "2026-11-02", 10000, 2),
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

    assert [row.outbound_date.isoformat() for row in first.results] == ["2026-11-01", "2026-11-02", "2026-11-05", "2026-11-03"]
    assert [str(row.total_miles) for row in first.results] == ["28000", "28000", "35000", "25000"]
    refs = [json.loads(row.raw_refs) for row in first.results]
    assert [ref["connection_status"] for ref in refs] == ["connected", "connected", "unverified", "unconnectable"]
    assert [ref["bucket_verified"] for ref in refs] == [True, True, False, False]
    assert "2026-11-04" not in {row.outbound_date.isoformat() for row in first.results}
    first_segments = json.loads(first.results[0].segments_json)
    boundary_segments = json.loads(first.results[1].segments_json)
    assert first_segments[0]["trip_id"] == "s1-d1-connects"
    assert first_segments[0]["connection_minutes"] == 180
    assert first_segments[0]["departs_at"] == "2026-11-01T07:00:00Z"
    assert first_segments[0]["arrives_at"] == "2026-11-01T11:00:00Z"
    assert first_segments[0]["flight_numbers"] == "s1-d1-connects"
    assert first_segments[0]["taxes"] == "35.60 USD"
    assert boundary_segments[0]["connection_minutes"] == 120
    assert second.created_results == 0
    assert client.cached_calls == [("TPE", "SIN"), ("SIN", "MLE")]
    assert client.trip_calls == ["s1-d3", "s2-d3", "s1-d2", "s2-d2", "s1-d4", "s1-d1", "s2-d1", "s1-d5", "s2-d5"]
    detail_notes = list(session.scalars(select(AwardWatch.note).where(AwardWatch.note.like("seats_trip_detail:%"))))
    assert detail_notes
    assert all(note.startswith("seats_trip_detail:business:") for note in detail_notes)


def make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
