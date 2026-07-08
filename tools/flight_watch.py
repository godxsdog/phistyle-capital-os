#!/usr/bin/env python3
"""Zero-dependency flight watcher for AK1511.

Data source:
  Fukuoka Airport official flight JSON:
  https://www.fukuoka-airport.jp/api/flight_schedule/flight_schedule.json

Notes:
  Flightradar24's common flight list endpoint was tested first, but returned
  a Cloudflare 403 from a plain Python request. This watcher therefore uses
  the Fukuoka Airport JSON feed, because AK1511 departs from FUK.

Mac mini setup:
  1. git pull on ~/Server/phistyle-capital-os
  2. Create ~/.flight_watch_env with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID,
     then chmod 600 ~/.flight_watch_env
  3. crontab -e, then add:
     */30 * * * * . ~/.flight_watch_env && cd ~/Server/phistyle-capital-os && /usr/bin/python3 tools/flight_watch.py AK1511 2026-07-10 >> /tmp/flight_watch.log 2>&1

Manual checks:
  . ~/.flight_watch_env && python3 tools/flight_watch.py --test-telegram
  python3 tools/flight_watch.py AK1511 2026-07-10 --print-status

This tool stores only transient state in /tmp/flight_watch_state.json.
It does not write credentials, browser artifacts, or repository data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_FLIGHT_NO = "AK1511"
DEFAULT_FLIGHT_DATE = "2026-07-10"
STATE_PATH = "/tmp/flight_watch_state.json"
FUKUOKA_SCHEDULE_URL = "https://www.fukuoka-airport.jp/api/flight_schedule/flight_schedule.json"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
FETCH_TIMEOUT_SECONDS = 25
FAIL_ALERT_THRESHOLD = 3


class WatchError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch a flight status and notify Telegram on changes.")
    parser.add_argument("flight_no", nargs="?", default=DEFAULT_FLIGHT_NO, help="Flight number, e.g. AK1511.")
    parser.add_argument("flight_date", nargs="?", default=DEFAULT_FLIGHT_DATE, help="Flight date in YYYY-MM-DD.")
    parser.add_argument("--test-telegram", action="store_true", help="Send a Telegram test message and exit.")
    parser.add_argument("--print-status", action="store_true", help="Fetch and print the current normalized status.")
    args = parser.parse_args()

    flight_no = args.flight_no.upper().replace(" ", "")
    flight_date = args.flight_date

    if args.test_telegram:
        send_telegram(f"{flight_no} 監視器測試：Telegram 通知已打通。")
        print("Telegram test message sent.")
        return 0

    state = load_state()
    try:
        status = fetch_fukuoka_status(flight_no, flight_date)
    except Exception as exc:  # noqa: BLE001 - fail-loud monitor must catch fetch/parse failures.
        if args.print_status:
            raise WatchError(str(exc)) from exc
        handle_failure(state, exc, flight_no, flight_date)
        return 1

    if args.print_status:
        print(status_display(status))
        return 0

    handle_success(state, status)
    return 0


def fetch_fukuoka_status(flight_no: str, flight_date: str) -> dict[str, Any]:
    payload = http_json(
        "GET",
        FUKUOKA_SCHEDULE_URL,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,zh-TW;q=0.7",
            "Referer": "https://www.fukuoka-airport.jp/en/flight/",
            "User-Agent": "Mozilla/5.0 flight-watch/2.0",
        },
    )
    if not isinstance(payload, dict):
        raise WatchError("Fukuoka Airport schedule response was not a JSON object")

    records = [record for record in payload.values() if isinstance(record, dict)]
    exact = [record for record in records if is_matching_flight(record, flight_no, flight_date)]
    if exact:
        return normalize_fukuoka_record(exact[0], flight_no, flight_date)

    source_dates = sorted({str(record.get("flt_ymd")) for record in records if record.get("flt_ymd")})
    same_flight = [record for record in records if is_matching_flight_number(record, flight_no)]
    if source_dates and flight_date not in source_dates:
        return {
            "flight_no": flight_no,
            "flight_date": flight_date,
            "status": "not_available_yet",
            "status_text": f"官方資料尚未提供 {flight_date}，目前資料日期:{', '.join(source_dates)}",
            "scheduled_departure": None,
            "estimated_departure": None,
            "actual_departure": None,
            "scheduled_arrival": None,
            "estimated_arrival": None,
            "origin": "FUK",
            "destination": best_destination(same_flight),
            "checked_at": utc_now(),
            "source": "fukuoka_airport_schedule_json",
            "source_dates": source_dates,
        }

    return {
        "flight_no": flight_no,
        "flight_date": flight_date,
        "status": "not_listed",
        "status_text": "指定日期的官方航班清單未列出此航班，請人工複查。",
        "scheduled_departure": None,
        "estimated_departure": None,
        "actual_departure": None,
        "scheduled_arrival": None,
        "estimated_arrival": None,
        "origin": "FUK",
        "destination": best_destination(same_flight),
        "checked_at": utc_now(),
        "source": "fukuoka_airport_schedule_json",
        "source_dates": source_dates,
    }


def query_status(flight_no: str, flight_date: str) -> dict[str, Any]:
    """Importable entry point for callers other than the CLI (e.g. the backend
    /tools/flight-status endpoint). Normalizes the flight number the same way
    main() does, fetches the current status, and returns both the raw
    normalized record and a human-readable display string so callers don't
    need to duplicate classify_status/status_display wiring.
    """
    normalized_flight_no = flight_no.upper().replace(" ", "")
    status = fetch_fukuoka_status(normalized_flight_no, flight_date)
    return {
        "flight_no": normalized_flight_no,
        "flight_date": flight_date,
        "status": status.get("status"),
        "display": status_display(status),
        "raw": status,
    }


def http_json(method: str, url: str, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> Any:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8", "replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise WatchError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except URLError as exc:
        raise WatchError(f"Network error from {url}: {exc.reason}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise WatchError(f"Non-JSON response from {url}: {text[:300]}") from exc


def is_matching_flight(record: dict[str, Any], flight_no: str, flight_date: str) -> bool:
    return is_matching_flight_number(record, flight_no) and record.get("flt_ymd") == flight_date


def is_matching_flight_number(record: dict[str, Any], flight_no: str) -> bool:
    airline, number = split_flight_no(flight_no)
    record_airline = str(record.get("airline_2cd") or "").upper()
    record_number = str(record.get("flt_num_no") or "").lstrip("0")
    return record_airline == airline and record_number == number.lstrip("0")


def split_flight_no(flight_no: str) -> tuple[str, str]:
    airline = "".join(ch for ch in flight_no if ch.isalpha())
    number = "".join(ch for ch in flight_no if ch.isdigit())
    if not airline or not number:
        raise WatchError(f"Invalid flight number: {flight_no}")
    return airline.upper(), number


def normalize_fukuoka_record(record: dict[str, Any], flight_no: str, flight_date: str) -> dict[str, Any]:
    scheduled_departure = fukuoka_time(record.get("flt_ymd"), record.get("appointed_time"))
    estimated_departure = fukuoka_datetime(record.get("estimated_ymdhm"))
    actual_departure = fukuoka_datetime(record.get("true_ymdhm"))
    status_text = stringify(record.get("remarks2")) or stringify(record.get("remarks")) or "On Time"
    normalized = classify_status(status_text, scheduled_departure, estimated_departure, actual_departure)
    return {
        "flight_no": flight_no,
        "flight_date": flight_date,
        "status": normalized,
        "status_text": status_text,
        "scheduled_departure": scheduled_departure,
        "estimated_departure": estimated_departure,
        "actual_departure": actual_departure,
        "scheduled_arrival": None,
        "estimated_arrival": None,
        "origin": "FUK" if record.get("deparv_div") == "D" else best_destination([record]),
        "destination": best_destination([record]) if record.get("deparv_div") == "D" else "FUK",
        "checked_at": utc_now(),
        "source": "fukuoka_airport_schedule_json",
        "raw_status_code": stringify(record.get("flt_sts")),
    }


def fukuoka_time(date_text: Any, hhmm: Any) -> str | None:
    date_value = stringify(date_text)
    time_value = stringify(hhmm)
    if not date_value or not time_value:
        return None
    padded = time_value.zfill(4)
    return f"{date_value} {padded[:2]}:{padded[2:]}"


def fukuoka_datetime(value: Any) -> str | None:
    text = stringify(value)
    if not text or len(text) < 12:
        return None
    return f"{text[:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}"


def classify_status(
    status_text: str | None,
    scheduled_departure: str | None,
    estimated_departure: str | None,
    actual_departure: str | None,
) -> str:
    text = (status_text or "").lower()
    if "cancel" in text or "欠航" in text or "取消" in text:
        return "cancelled"
    if "departed" in text or "出発済" in text:
        return "departed"
    if "arrived" in text or "到着済" in text:
        return "arrived"
    if "delay" in text or "delayed" in text or "遅延" in text or "延誤" in text:
        return "delayed"
    if scheduled_departure and estimated_departure and time_part(scheduled_departure) != time_part(estimated_departure):
        return "time_changed"
    if actual_departure:
        return "departed"
    return "scheduled"


def best_destination(records: list[dict[str, Any]]) -> str | None:
    for record in records:
        value = stringify(record.get("tofrom_cd")) or stringify(record.get("tofrom_name2")) or stringify(record.get("tofrom_name4"))
        if value:
            return value
    return None


def stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def handle_success(state: dict[str, Any], status: dict[str, Any]) -> None:
    new_signature = status_signature(status)
    old_signature = state.get("last_signature")
    old_status = state.get("last_status")
    flight_no = str(status.get("flight_no") or DEFAULT_FLIGHT_NO)
    flight_date = str(status.get("flight_date") or DEFAULT_FLIGHT_DATE)
    if not state.get("startup_sent"):
        send_telegram(f"{flight_no}({flight_date})監視器已上線，目前狀態:{status_display(status)}")
        state["startup_sent"] = True
    elif old_signature and old_signature != new_signature:
        send_telegram(f"⚠️ {flight_no}({flight_date})狀態變更:{status_display(old_status)} → {status_display(status)}")
    state["last_signature"] = new_signature
    state["last_status"] = status
    state["fail_count"] = 0
    state["last_failure_alert_count"] = 0
    state.pop("last_error", None)
    state.pop("last_error_at", None)
    save_state(state)


def handle_failure(state: dict[str, Any], exc: Exception, flight_no: str, flight_date: str) -> None:
    fail_count = int(state.get("fail_count", 0)) + 1
    state["fail_count"] = fail_count
    state["last_error"] = str(exc)
    state["last_error_at"] = utc_now()
    last_alert_count = int(state.get("last_failure_alert_count", 0))
    if fail_count >= FAIL_ALERT_THRESHOLD and last_alert_count != fail_count:
        send_telegram(f"⚠️ {flight_no}({flight_date})監視器故障,請自行查航班。連續失敗 {fail_count} 次。錯誤:{exc}")
        state["last_failure_alert_count"] = fail_count
    save_state(state)
    print(f"flight watch failed ({fail_count}): {exc}", file=sys.stderr)


def status_signature(status: dict[str, Any]) -> str:
    keys = [
        "status",
        "status_text",
        "scheduled_departure",
        "estimated_departure",
        "actual_departure",
        "scheduled_arrival",
        "estimated_arrival",
        "origin",
        "destination",
    ]
    return json.dumps({key: status.get(key) for key in keys}, ensure_ascii=False, sort_keys=True)


def status_display(status: Any) -> str:
    if not isinstance(status, dict):
        return "未知"
    normalized = status.get("status") or "scheduled"
    if normalized == "cancelled":
        return "❌ 已取消"
    if normalized in {"delayed", "time_changed"}:
        time_text = time_part(status.get("estimated_departure")) or status.get("estimated_departure") or "未提供時間"
        return f"🕐 延誤至 {time_text}"
    if normalized == "not_available_yet":
        return str(status.get("status_text") or "官方資料尚未提供")
    if normalized == "not_listed":
        return str(status.get("status_text") or "官方清單未列出")
    return str(status.get("status_text") or normalized)


def time_part(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(value[: len(fmt)], fmt).strftime("%H:%M")
        except ValueError:
            pass
    if len(value) >= 5 and value[-5:-2] == ":":
        return value[-5:]
    return value


def send_telegram(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise WatchError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    url = TELEGRAM_API.format(token=token)
    payload = {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
    http_json("POST", url, headers={"Content-Type": "application/json"}, payload=payload)


def load_state() -> dict[str, Any]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {"corrupt_state_replaced_at": utc_now()}


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    tmp_path = f"{STATE_PATH}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp_path, STATE_PATH)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WatchError as error:
        print(f"flight_watch error: {error}", file=sys.stderr)
        time.sleep(0.2)
        raise SystemExit(2)
