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
from shared.models import tool_monitor  # noqa: F401
from shared.services.tool_monitor_service import MonitorTickResult


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


def test_get_flight_watch_settings_creates_default_row():
    client = make_client()

    response = client.get("/tools/monitors/flight_watch")

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "flight_watch"
    assert payload["enabled"] is False
    assert payload["flight_no"] == "AK1511"
    assert payload["flight_date"] == "2026-07-10"
    assert payload["interval_minutes"] == 30


def test_patch_flight_watch_settings_updates_fields():
    client = make_client()

    response = client.patch(
        "/tools/monitors/flight_watch",
        json={"enabled": True, "flight_no": "ak1511", "interval_minutes": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["flight_no"] == "AK1511"
    assert payload["interval_minutes"] == 10


def test_patch_flight_watch_settings_rejects_invalid_interval():
    client = make_client()

    response = client.patch("/tools/monitors/flight_watch", json={"interval_minutes": 45})

    assert response.status_code == 422


def test_post_flight_status_uses_mocked_query(monkeypatch):
    client = make_client()

    def fake_query(flight_no, flight_date):
        return {
            "flight_no": flight_no,
            "flight_date": flight_date,
            "status": "scheduled",
            "display": "準時",
            "raw": {"status": "scheduled"},
        }

    monkeypatch.setattr("backend.app.main.query_flight_status", fake_query)

    response = client.post("/tools/flight-status", json={"flight_no": "AK1511", "flight_date": "2026-07-10"})

    assert response.status_code == 200
    assert response.json()["display"] == "準時"


def test_post_flight_status_returns_502_on_fetch_failure(monkeypatch):
    client = make_client()

    def fake_query(flight_no, flight_date):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr("backend.app.main.query_flight_status", fake_query)

    response = client.post("/tools/flight-status", json={"flight_no": "AK1511", "flight_date": "2026-07-10"})

    assert response.status_code == 502


def test_post_monitor_tick_uses_mocked_tick(monkeypatch):
    client = make_client()

    def fake_tick(session):
        return MonitorTickResult(skipped=True, reason="disabled", ran_at=None, status_ok=None, display=None, notified=False)

    monkeypatch.setattr("backend.app.main.tick_flight_watch", fake_tick)

    response = client.post("/tools/monitors/tick")

    assert response.status_code == 200
    assert response.json() == {
        "skipped": True,
        "reason": "disabled",
        "ran_at": None,
        "status_ok": None,
        "display": None,
        "notified": False,
    }
