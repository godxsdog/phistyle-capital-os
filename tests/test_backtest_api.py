from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import backtest, market_data  # noqa: F401
from shared.models.market_data import MarketDailyBar


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    seed_bars(session_factory())

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


def seed_bars(session) -> None:
    closes = [Decimal("10"), Decimal("10"), Decimal("10"), Decimal("12"), Decimal("14"), Decimal("13"), Decimal("12"), Decimal("11"), Decimal("10"), Decimal("9")]
    for offset, close in enumerate(closes):
        session.add(
            MarketDailyBar(
                market="taifex",
                symbol="TX",
                bar_date=date(2026, 1, 1) + timedelta(days=offset),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=100,
                open_interest=1000,
                source="fixture",
            )
        )
    session.commit()
    session.close()


def sma_payload() -> dict:
    return {
        "spec": {
            "name": "api sma cross",
            "market": "taifex",
            "symbol": "TX",
            "direction": "long",
            "entry": {"type": "sma_cross", "fast": 2, "slow": 3},
            "exit": {"target_pct": 0.1, "opposite_signal": False},
        }
    }


def test_backtest_api_run_list_get_and_idempotency():
    client = make_client()

    first = client.post("/capital/backtests/run", json=sma_payload())
    second = client.post("/capital/backtests/run", json=sma_payload())
    runs = client.get("/capital/backtests/runs")
    specs = client.get("/capital/backtests/specs")
    detail = client.get(f"/capital/backtests/runs/{first.json()['id']}")

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert first.json()["id"] == second.json()["id"]
    assert len(runs.json()) == 1
    assert specs.json()[0]["name"] == "api sma cross"
    assert detail.json()["results"]["full"]["trades"][0]["net_pnl"] == "-100.10"


def test_backtest_run_is_immutable_through_api_surface():
    client = make_client()
    created = client.post("/capital/backtests/run", json=sma_payload())

    patch = client.patch(f"/capital/backtests/runs/{created.json()['id']}", json={"results": {}})
    delete = client.delete(f"/capital/backtests/runs/{created.json()['id']}")

    assert patch.status_code == 405
    assert delete.status_code == 405
