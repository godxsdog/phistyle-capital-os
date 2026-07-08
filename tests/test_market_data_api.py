from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import market_data  # noqa: F401


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
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


def test_market_watchlist_crud_and_sanity():
    client = make_client()

    created = client.post("/capital/market-data/watchlist", json={"market": "us", "symbol": "aapl.us", "active": True})

    assert created.status_code == 200
    assert created.json()["symbol"] == "AAPL"
    assert client.get("/capital/market-data/watchlist").json()[0]["active"] is True

    patched = client.patch(
        f"/capital/market-data/watchlist/{created.json()['id']}",
        json={"market": "us", "symbol": "AAPL", "active": False},
    )
    assert patched.json()["active"] is False

    sanity = client.get("/capital/market-data/sanity")
    assert sanity.status_code == 200
    assert sanity.json() == []

    deleted = client.delete(f"/capital/market-data/watchlist/{created.json()['id']}")
    assert deleted.json() == {"deleted": True}


def test_market_ingest_endpoint_uses_mocked_services(monkeypatch):
    client = make_client()

    class FakeResult:
        source = "yahoo"
        status = "success"
        inserted = 2
        skipped = 1
        warnings: list[str] = []

    def fake_ingest(session):
        return FakeResult()

    monkeypatch.setattr("backend.app.main.ingest_yahoo_us", fake_ingest)

    response = client.post("/capital/market-data/ingest", json={"source": "yahoo"})

    assert response.status_code == 200
    assert response.json()["results"][0]["inserted"] == 2
