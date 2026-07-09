from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import decision_request, knowledge, market_data, trade_plan  # noqa: F401


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


def test_trade_plan_create_routes_to_existing_decision_pipeline_shape():
    client = make_client()

    response = client.post("/capital/trade-plans", json=plan_payload(stop_price="19900"))

    assert response.status_code == 200
    body = response.json()
    assert body["decision_request_risk_level"] == "high"
    request = client.get(f"/capital/decisions/{body['decision_request_id']}")
    assert request.status_code == 200
    assert request.json()["requires_human_review"] is False


def test_trade_plan_list_mark_close_and_stats():
    client = make_client()
    created = client.post("/capital/trade-plans", json=plan_payload()).json()

    assert client.get("/capital/trade-plans").json()[0]["id"] == created["id"]

    close = client.post(f"/capital/trade-plans/{created['id']}/close", json={"exit_price": "20050", "notes": "manual close"})
    stats = client.get("/capital/trade-plans/stats")

    assert close.status_code == 200
    assert close.json()["gross_pnl"] == "10000.00"
    assert close.json()["currency"] == "TWD"
    assert stats.json()["by_currency"][0]["currency"] == "TWD"


def plan_payload(**overrides):
    payload = {
        "market": "taifex",
        "symbol": "TX",
        "direction": "long",
        "planned_entry": "20000",
        "stop_price": "19980",
        "target_price": "20200",
        "quantity": "1",
        "declared_capital_twd": "500000",
        "thesis": "synthetic paper trade",
        "is_paper": True,
        "created_by": "Kaichang",
    }
    payload.update(overrides)
    return payload
