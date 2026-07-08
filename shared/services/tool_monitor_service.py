from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.tool_monitor import ToolMonitorSetting
from tools.flight_watch import query_status as fetch_flight_status_default
from tools.flight_watch import send_telegram as send_telegram_default
from tools.flight_watch import status_signature


FLIGHT_WATCH_KIND = "flight_watch"
DEFAULT_FLIGHT_NO = "AK1511"
DEFAULT_FLIGHT_DATE = date(2026, 7, 10)
ALLOWED_INTERVAL_MINUTES = {10, 20, 30, 60}
FAIL_ALERT_THRESHOLD = 3


class ToolMonitorError(ValueError):
    pass


@dataclass(frozen=True)
class MonitorTickResult:
    skipped: bool
    reason: str | None
    ran_at: datetime | None
    status_ok: bool | None
    display: str | None
    notified: bool


def get_or_create_flight_watch_settings(session: Session) -> ToolMonitorSetting:
    row = session.scalars(select(ToolMonitorSetting).where(ToolMonitorSetting.kind == FLIGHT_WATCH_KIND)).first()
    if row is not None:
        return row
    row = ToolMonitorSetting(
        kind=FLIGHT_WATCH_KIND,
        enabled=False,
        flight_no=DEFAULT_FLIGHT_NO,
        flight_date=DEFAULT_FLIGHT_DATE,
        interval_minutes=30,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_flight_watch_settings(
    session: Session,
    *,
    enabled: bool | None = None,
    flight_no: str | None = None,
    flight_date: date | None = None,
    interval_minutes: int | None = None,
) -> ToolMonitorSetting:
    row = get_or_create_flight_watch_settings(session)
    if enabled is not None:
        row.enabled = enabled
    if flight_no is not None:
        cleaned = flight_no.strip().upper().replace(" ", "")
        if not cleaned:
            raise ToolMonitorError("flight_no must not be empty")
        row.flight_no = cleaned
    if flight_date is not None:
        row.flight_date = flight_date
    if interval_minutes is not None:
        if interval_minutes not in ALLOWED_INTERVAL_MINUTES:
            raise ToolMonitorError("interval_minutes must be one of 10, 20, 30, 60")
        row.interval_minutes = interval_minutes
    session.commit()
    session.refresh(row)
    return row


def query_flight_status(
    flight_no: str,
    flight_date: str,
    fetcher: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One-off query used by POST /tools/flight-status. Delegates to
    tools.flight_watch.query_status (stdlib urllib, no CLI side effects)."""
    fetcher = fetcher or fetch_flight_status_default
    return fetcher(flight_no, flight_date)


def tick_flight_watch(
    session: Session,
    *,
    now: datetime | None = None,
    fetcher: Callable[[str, str], dict[str, Any]] | None = None,
    notifier: Callable[[str], None] | None = None,
) -> MonitorTickResult:
    """Runs the flight_watch monitor once, honoring the enabled flag and
    interval_minutes gate. Never raises: fetch failures are recorded on the
    settings row and surfaced via last_status, mirroring the standalone
    tools/flight_watch.py CLI's fail-loud-but-don't-crash behavior.
    """
    fetcher = fetcher or fetch_flight_status_default
    notifier = notifier or send_telegram_default
    now = now or datetime.now(timezone.utc)

    settings = get_or_create_flight_watch_settings(session)
    if not settings.enabled:
        return MonitorTickResult(skipped=True, reason="disabled", ran_at=None, status_ok=None, display=None, notified=False)

    if settings.last_run_at is not None:
        elapsed = now - _as_aware(settings.last_run_at)
        if elapsed < timedelta(minutes=settings.interval_minutes):
            return MonitorTickResult(skipped=True, reason="interval_not_elapsed", ran_at=None, status_ok=None, display=None, notified=False)

    previous_state = _parse_last_status(settings.last_status)
    notified = False
    try:
        result = fetcher(settings.flight_no, settings.flight_date.isoformat())
        raw = result.get("raw")
        signature = status_signature(raw) if isinstance(raw, dict) else json.dumps(result.get("status"))
        display = result.get("display") or ""
        previous_ok = previous_state.get("ok") if previous_state else None
        previous_signature = previous_state.get("signature") if previous_state else None
        if previous_ok is True and previous_signature is not None and previous_signature != signature:
            _notify(notifier, f"⚠️ {settings.flight_no}({settings.flight_date.isoformat()}) 狀態變更：{display}")
            notified = True
        new_state = {
            "ok": True,
            "status": result.get("status"),
            "display": display,
            "signature": signature,
            "fail_count": 0,
            "alerted_at_count": 0,
        }
        settings.last_status = json.dumps(new_state, ensure_ascii=False)
        settings.last_run_at = now
        session.commit()
        return MonitorTickResult(skipped=False, reason=None, ran_at=now, status_ok=True, display=display, notified=notified)
    except Exception as exc:  # noqa: BLE001 - monitor tick must never crash the caller
        previous_fail_count = (
            previous_state.get("fail_count", 0) if previous_state and not previous_state.get("ok", True) else 0
        )
        fail_count = previous_fail_count + 1
        alerted_at_count = previous_state.get("alerted_at_count", 0) if previous_state else 0
        message = str(exc)
        if fail_count >= FAIL_ALERT_THRESHOLD and alerted_at_count != fail_count:
            _notify(notifier, f"⚠️ {settings.flight_no}({settings.flight_date.isoformat()}) 監控連續失敗 {fail_count} 次：{message}")
            notified = True
            alerted_at_count = fail_count
        new_state = {
            "ok": False,
            "status": None,
            "display": None,
            "signature": None,
            "fail_count": fail_count,
            "alerted_at_count": alerted_at_count,
            "error": message,
        }
        settings.last_status = json.dumps(new_state, ensure_ascii=False)
        settings.last_run_at = now
        session.commit()
        return MonitorTickResult(skipped=False, reason=None, ran_at=now, status_ok=False, display=message, notified=notified)


def parse_last_status(raw: str | None) -> dict[str, Any] | None:
    return _parse_last_status(raw)


def _notify(notifier: Callable[[str], None], message: str) -> None:
    try:
        notifier(message)
    except Exception:  # noqa: BLE001 - best-effort notification only, never fails the tick
        pass


def _parse_last_status(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
