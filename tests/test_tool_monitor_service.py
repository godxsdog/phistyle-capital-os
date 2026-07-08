from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import tool_monitor  # noqa: F401
from shared.services.tool_monitor_service import (
    ToolMonitorError,
    get_or_create_flight_watch_settings,
    parse_last_status,
    tick_flight_watch,
    update_flight_watch_settings,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return factory()


def ok_result(status: str, display: str) -> dict:
    return {
        "flight_no": "AK1511",
        "flight_date": "2026-07-10",
        "status": status,
        "display": display,
        "raw": {
            "status": status,
            "status_text": display,
            "scheduled_departure": "2026-07-10 08:00",
            "estimated_departure": "2026-07-10 08:00",
            "actual_departure": None,
            "scheduled_arrival": None,
            "estimated_arrival": None,
            "origin": "FUK",
            "destination": "TPE",
        },
    }


def test_get_or_create_default_settings_uses_ticket_defaults():
    session = make_session()

    row = get_or_create_flight_watch_settings(session)

    assert row.kind == "flight_watch"
    assert row.enabled is False
    assert row.flight_no == "AK1511"
    assert row.flight_date == date(2026, 7, 10)
    assert row.interval_minutes == 30

    # idempotent: calling again returns the same row, not a duplicate.
    again = get_or_create_flight_watch_settings(session)
    assert again.id == row.id


def test_update_settings_rejects_invalid_interval():
    session = make_session()

    with pytest.raises(ToolMonitorError):
        update_flight_watch_settings(session, interval_minutes=45)


def test_update_settings_normalizes_flight_no():
    session = make_session()

    row = update_flight_watch_settings(session, flight_no=" ak1511 ", enabled=True, interval_minutes=10)

    assert row.flight_no == "AK1511"
    assert row.enabled is True
    assert row.interval_minutes == 10


def test_tick_skipped_when_disabled():
    session = make_session()

    result = tick_flight_watch(session, fetcher=lambda *_: ok_result("scheduled", "準時"), notifier=lambda *_: None)

    assert result.skipped is True
    assert result.reason == "disabled"


def test_tick_skipped_when_interval_not_elapsed():
    session = make_session()
    update_flight_watch_settings(session, enabled=True, interval_minutes=30)
    now = datetime.now(timezone.utc)
    fetcher_calls = []

    def fetcher(flight_no, flight_date):
        fetcher_calls.append((flight_no, flight_date))
        return ok_result("scheduled", "準時")

    first = tick_flight_watch(session, now=now, fetcher=fetcher, notifier=lambda *_: None)
    assert first.skipped is False
    assert len(fetcher_calls) == 1

    second = tick_flight_watch(session, now=now + timedelta(minutes=5), fetcher=fetcher, notifier=lambda *_: None)
    assert second.skipped is True
    assert second.reason == "interval_not_elapsed"
    assert len(fetcher_calls) == 1  # no extra fetch when skipped


def test_tick_runs_after_interval_elapses():
    session = make_session()
    update_flight_watch_settings(session, enabled=True, interval_minutes=10)
    now = datetime.now(timezone.utc)

    tick_flight_watch(session, now=now, fetcher=lambda *_: ok_result("scheduled", "準時"), notifier=lambda *_: None)
    second = tick_flight_watch(
        session,
        now=now + timedelta(minutes=11),
        fetcher=lambda *_: ok_result("scheduled", "準時"),
        notifier=lambda *_: None,
    )

    assert second.skipped is False


def test_tick_notifies_on_status_change_but_not_on_first_success():
    session = make_session()
    update_flight_watch_settings(session, enabled=True, interval_minutes=10)
    now = datetime.now(timezone.utc)
    notifications: list[str] = []

    first = tick_flight_watch(
        session,
        now=now,
        fetcher=lambda *_: ok_result("scheduled", "準時"),
        notifier=notifications.append,
    )
    assert first.notified is False
    assert notifications == []

    second = tick_flight_watch(
        session,
        now=now + timedelta(minutes=11),
        fetcher=lambda *_: ok_result("delayed", "延誤"),
        notifier=notifications.append,
    )
    assert second.notified is True
    assert len(notifications) == 1
    assert "延誤" in notifications[0]


def test_tick_alerts_after_three_consecutive_failures_and_not_again_on_fourth():
    session = make_session()
    update_flight_watch_settings(session, enabled=True, interval_minutes=10)
    now = datetime.now(timezone.utc)
    notifications: list[str] = []

    def failing_fetcher(*_):
        raise RuntimeError("network unreachable")

    def force_gate_open():
        # Bypass the interval gate (without touching validation) by clearing
        # last_run_at directly, so each tick below runs regardless of the
        # real interval_minutes value.
        settings = get_or_create_flight_watch_settings(session)
        settings.last_run_at = None
        session.commit()

    for i in range(3):
        force_gate_open()
        tick_flight_watch(
            session,
            now=now + timedelta(minutes=2 * i),
            fetcher=failing_fetcher,
            notifier=notifications.append,
        )

    assert len(notifications) == 1  # only alerted once, on the 3rd consecutive failure

    row = get_or_create_flight_watch_settings(session)
    state = parse_last_status(row.last_status)
    assert state is not None
    assert state["ok"] is False
    assert state["fail_count"] == 3

    # A 4th consecutive failure bumps fail_count to 4, which differs from the
    # alerted_at_count(3) recorded above, so it alerts again. This mirrors
    # tools/flight_watch.py's own CLI debounce (dedupes only same-count
    # re-processing, not repeated failures at increasing counts).
    force_gate_open()
    tick_flight_watch(
        session,
        now=now + timedelta(minutes=10),
        fetcher=failing_fetcher,
        notifier=notifications.append,
    )
    assert len(notifications) == 2


def test_tick_never_raises_and_records_error_in_last_status():
    session = make_session()
    update_flight_watch_settings(session, enabled=True, interval_minutes=10)

    def failing_fetcher(*_):
        raise ValueError("boom")

    result = tick_flight_watch(session, fetcher=failing_fetcher, notifier=lambda *_: None)

    assert result.skipped is False
    assert result.status_ok is False
    row = get_or_create_flight_watch_settings(session)
    state = parse_last_status(row.last_status)
    assert state["error"] == "boom"
