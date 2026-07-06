from datetime import date

import pytest


pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def create_program(client, name="Aeroplan"):
    response = client.post("/wallet/programs", json={"name": name, "kind": "airline"})
    assert response.status_code == 200
    return response.json()


def test_wallet_stage_one_endpoints_compute_portfolio_and_expiry():
    client = make_client()
    program = create_program(client)

    assert client.post(
        "/wallet/balances",
        json={
            "program_id": program["id"],
            "balance": "10000",
            "as_of": "2026-07-01",
            "expires_at": "2026-08-01",
        },
    ).status_code == 200
    assert client.post(
        "/wallet/valuations",
        json={
            "program_id": program["id"],
            "twd_per_point": "0.300000",
            "effective_date": "2026-07-01",
            "source": "editable defaults, not market truth",
        },
    ).status_code == 200

    portfolio = client.get("/wallet/portfolio").json()

    assert portfolio["total_value_twd"] == "3000.00000000"
    assert portfolio["programs"][0]["program_name"] == "Aeroplan"
    assert portfolio["expiring_soon"][0]["expires_at"] == "2026-08-01"


def test_transfer_watch_manual_availability_and_mocked_fetch(monkeypatch):
    client = make_client()
    bank = create_program(client, "Bank Points")
    airline = create_program(client, "Aeroplan")

    transfer = client.post(
        "/wallet/transfers",
        json={
            "from_program_id": bank["id"],
            "to_program_id": airline["id"],
            "ratio_from": 1,
            "ratio_to": 1,
            "transfer_days": "instant",
        },
    )
    assert transfer.status_code == 200
    watch = client.post(
        "/wallet/watches",
        json={"origin": "TPE", "destination": "LAX", "cabin": "business", "program_id": airline["id"]},
    )
    assert watch.status_code == 200
    manual = client.post(
        "/wallet/availability",
        json={
            "watch_id": watch.json()["id"],
            "seen_date": "2026-07-06",
            "flight_date": "2026-10-01",
            "program": "Aeroplan",
            "seats": 2,
            "miles_cost": "75000",
            "taxes_fees": "CAD 88",
            "source": "manual",
        },
    )
    assert manual.status_code == 200

    def mock_fetch(session, *, watch_id):
        assert watch_id == watch.json()["id"]
        return {"created": 1}

    monkeypatch.setattr(main, "fetch_award_watch", mock_fetch)
    fetched = client.post(f"/wallet/watches/{watch.json()['id']}/fetch")

    assert fetched.status_code == 200
    assert fetched.json() == {"created": 1}
    assert client.get("/wallet/transfers").json()[0]["ratio_from"] == 1
    assert client.get("/wallet/availability").json()[0]["source"] == "manual"


def test_registry_marks_points_wallet_scaffold_active():
    client = make_client()

    apps = client.get("/apps").json()
    wallet = next(app for app in apps if app["id"] == "points-wallet")

    assert wallet["status"] == "scaffold-active"
    assert wallet["route"] == "/wallet"
