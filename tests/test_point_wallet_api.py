from datetime import date

import pytest


pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def test_wallet_routes_create_account_lot_and_portfolio():
    client = make_client()
    program = client.post("/wallet/programs", json={"name": "Aeroplan", "kind": "airline"}).json()
    account = client.post(
        "/wallet/accounts",
        json={"owner": "kent", "program_id": program["id"], "account_ref": "123456789"},
    ).json()
    response = client.post(
        "/wallet/ledger",
        json={
            "account_id": account["id"],
            "kind": "buy",
            "quantity": "10000",
            "occurred_at": "2026-07-06",
            "cost_total": "3100",
            "cost_currency": "TWD",
            "create_lot": True,
        },
    )

    assert response.status_code == 200
    portfolio = client.get("/wallet/portfolio?owner=kent").json()
    assert portfolio["total_real_cost_basis_twd"] == "3100.00"
    assert portfolio["accounts"][0]["balance"] == "10000.00"
    assert client.get("/wallet/accounts").json()[0]["account_ref"] == "***6789"


def test_wallet_transfer_rule_offer_fx_and_registry_contract(monkeypatch):
    client = make_client()
    wanlitong = client.post("/wallet/programs", json={"name": "平安萬里通", "kind": "bank"}).json()
    aeroplan = client.post("/wallet/programs", json={"name": "Aeroplan", "kind": "airline"}).json()

    rule = client.post(
        "/wallet/transfer-rules",
        json={
            "from_program_id": wanlitong["id"],
            "to_program_id": aeroplan["id"],
            "ratio_from": "3",
            "ratio_to": "1",
            "bonus_pct": "25",
            "valid_from": "2026-07-06",
        },
    )
    offer = client.post(
        "/wallet/purchase-offers",
        json={
            "program_id": aeroplan["id"],
            "kind": "official",
            "base_price": "0.5",
            "currency": "TWD",
            "bonus_pct": "25",
            "start_date": "2026-07-06",
        },
    )

    def fail_fetch():
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr("shared.services.exchange_rate_service._fetch_open_er_api_rates", fail_fetch)
    fx = client.post("/wallet/fx-rates/refresh")
    apps = client.get("/apps").json()
    wallet = next(app for app in apps if app["id"] == "points-wallet")

    assert rule.status_code == 200
    assert offer.json()["effective_cpp"] == "0.400000"
    assert fx.json()["source"] == "fallback"
    assert wallet["status"] == "scaffold-active"
    assert wallet["route"] == "/wallet"
