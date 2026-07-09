from __future__ import annotations

from datetime import date
from decimal import Decimal

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
from shared.services.point_wallet_service import create_account, create_hotel_voucher, create_ledger_transaction, create_program, list_cost_lots, list_hotel_vouchers


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
    seed(session_factory)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    return TestClient(app), session_factory


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def seed(session_factory):
    session = session_factory()
    marriott = create_program(session, name="Marriott Bonvoy", kind="hotel")
    account = create_account(session, owner="kent", program_id=marriott.id)
    create_ledger_transaction(
        session,
        account_id=account.id,
        kind="buy",
        quantity=Decimal("100000"),
        occurred_at=date(2026, 7, 1),
        cost_total=Decimal("20000"),
        cost_currency="TWD",
        create_lot=True,
    )
    create_hotel_voucher(session, owner="kent", program_id=marriott.id, face_value_points=Decimal("50000"), expires_at=date(2026, 8, 28))
    session.close()


def snapshots(session_factory):
    session = session_factory()
    try:
        lots = [(lot.id, lot.remaining_quantity, lot.total_cost_twd) for lot in list_cost_lots(session)]
        vouchers = [(voucher.id, voucher.status, voucher.used_note) for voucher in list_hotel_vouchers(session)]
        return lots, vouchers
    finally:
        session.close()


def test_hotel_quote_create_list_evaluate_is_read_only():
    client, session_factory = make_client()
    program = client.get("/wallet/programs").json()[0]
    before = snapshots(session_factory)

    created = client.post(
        "/wallet/hotel-stay-quotes",
        json={
            "owner": "kent",
            "hotel_name": "Synthetic Marriott",
            "stay_date": "2026-08-01",
            "nights": 1,
            "program_id": program["id"],
            "cash_price_twd": "12000",
            "points_price_per_night": "50000",
            "topup_allowed": False,
        },
    )
    listed = client.get("/wallet/hotel-stay-quotes")
    evaluated = client.post(f"/wallet/hotel-stay-quotes/{created.json()['id']}/evaluate")
    after = snapshots(session_factory)

    assert created.status_code == 200
    assert listed.status_code == 200
    assert listed.json()[0]["hotel_name"] == "Synthetic Marriott"
    assert evaluated.status_code == 200
    assert evaluated.json()["cpp"] == "0.240000"
    assert next(row for row in evaluated.json()["options"] if row["method"] == "voucher")["cash_cost_twd"] == "0.00"
    assert after == before
