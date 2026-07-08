#!/usr/bin/env python3
"""One-off flight cancellation watcher for AirAsia AK1511 on 2026-07-10.

Data source:
  AirAsia flightstatus page currently loads the JSON endpoint:
  https://flightstatusv5.airasia.com//api/v5/GetByFlightNumber

Mac mini setup:
  1. scp tools/flight_watch.py kaichanghuang@KaiChangdeMac-mini.local:/Users/kaichanghuang/Server/phistyle-capital-os/tools/flight_watch.py
  2. On the Mac mini, set environment values in the crontab line below:
     TELEGRAM_BOT_TOKEN=<bot token>
     TELEGRAM_CHAT_ID=<your chat id>
     Optional: AIRASIA_FLIGHTSTATUS_TOKEN=<Bearer token if AirAsia requires one>
  3. crontab -e, then add:
     */20 * * * * TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... /usr/bin/python3 /Users/kaichanghuang/Server/phistyle-capital-os/tools/flight_watch.py >> /tmp/flight_watch.log 2>&1

Telegram test:
  TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 tools/flight_watch.py --test-telegram

This tool intentionally stores only transient state in /tmp/flight_watch_state.json.
It does not write statement files, credentials, or repository data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FLIGHT_NO = "AK1511"
FLIGHT_DATE = "2026-07-10"
STATE_PATH = "/tmp/flight_watch_state.json"
AIRASIA_ENDPOINT = "https://flightstatusv5.airasia.com//api/v5/GetByFlightNumber"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
FETCH_TIMEOUT_SECONDS = 25
FAIL_ALERT_THRESHOLD = 3


class WatchError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch AK1511 flight status and notify Telegram on changes.")
    parser.add_argument("--test-telegram", action="store_true", help="Send a Telegram test message and exit.")
    parser.add_argument("--print-status", action="store_true", help="Fetch and print the current normalized status only.")
    args = parser.parse_args()

    if args.test_telegram:
        send_telegram("AK1511 監視器測試：Telegram 通知已打通。")
        print("Telegram test message sent.")
        return 0

    state = load_state()
    try:
        status = fetch_airasia_status()
    except Exception as exc:  # noqa: BLE001 - fail-loud monitor must catch all fetch/parse failures.
        if args.print_status:
            raise WatchError(str(exc)) from exc
        handle_failure(state, exc)
        return 1

    if args.print_status:
        print(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    handle_success(state, status)
    return 0


def fetch_airasia_status() -> dict[str, Any]:
    params = urlencode({"flightNo": FLIGHT_NO, "date": FLIGHT_DATE})
    url = f"{AIRASIA_ENDPOINT}?{params}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 flight-watch/1.0",
    }
    bearer_token = os.getenv("AIRASIA_FLIGHTSTATUS_TOKEN", "").strip()
    if bearer_token:
        headers["Authorization"] = bearer_token if bearer_token.lower().startswith("bearer ") else f"Bearer {bearer_token}"
    raw = http_json("GET", url, headers=headers)
    flight = find_flight_record(raw, FLIGHT_NO, FLIGHT_DATE)
    if flight is None:
        raise WatchError(f"AirAsia response did not contain {FLIGHT_NO} on {FLIGHT_DATE}")
    return normalize_flight_record(flight)


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


def find_flight_record(payload: Any, flight_no: str, flight_date: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    walk_json(payload, candidates)
    normalized_flight = compact(flight_no)
    for candidate in candidates:
        text = json.dumps(candidate, ensure_ascii=False).lower()
        if normalized_flight.lower() not in compact(text).lower():
            continue
        if flight_date in text or flight_date.replace("-", "/") in text or flight_date.replace("-", "") in text:
            return candidate
    if len(candidates) == 1 and normalized_flight.lower() in compact(json.dumps(candidates[0], ensure_ascii=False)).lower():
        return candidates[0]
    return None


def walk_json(value: Any, candidates: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        keys = {str(key).lower() for key in value}
        if any("flight" in key for key in keys) or any("status" in key for key in keys):
            candidates.append(value)
        for child in value.values():
            walk_json(child, candidates)
    elif isinstance(value, list):
        for child in value:
            walk_json(child, candidates)


def normalize_flight_record(record: dict[str, Any]) -> dict[str, Any]:
    status_text = first_text(record, ["status", "flightStatus", "statusName", "flightStatusName", "displayStatus"])
    scheduled_departure = first_text(record, ["std", "scheduledDeparture", "scheduledDepartureTime", "departureScheduledTime"])
    estimated_departure = first_text(record, ["etd", "estimatedDeparture", "estimatedDepartureTime", "departureEstimatedTime"])
    actual_departure = first_text(record, ["atd", "actualDeparture", "actualDepartureTime", "departureActualTime"])
    scheduled_arrival = first_text(record, ["sta", "scheduledArrival", "scheduledArrivalTime", "arrivalScheduledTime"])
    estimated_arrival = first_text(record, ["eta", "estimatedArrival", "estimatedArrivalTime", "arrivalEstimatedTime"])
    origin = first_text(record, ["origin", "departureStation", "departureAirport", "from"])
    destination = first_text(record, ["destination", "arrivalStation", "arrivalAirport", "to"])
    normalized = classify_status(status_text, scheduled_departure, estimated_departure)
    return {
        "flight_no": FLIGHT_NO,
        "flight_date": FLIGHT_DATE,
        "status": normalized,
        "status_text": status_text or normalized,
        "scheduled_departure": scheduled_departure,
        "estimated_departure": estimated_departure,
        "actual_departure": actual_departure,
        "scheduled_arrival": scheduled_arrival,
        "estimated_arrival": estimated_arrival,
        "origin": origin,
        "destination": destination,
        "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source": "airasia_flightstatus_json",
    }


def first_text(record: dict[str, Any], names: list[str]) -> str | None:
    lowered = {str(key).lower(): value for key, value in flatten_dict(record).items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is None:
            continue
        text = stringify(value)
        if text:
            return text
    return None


def flatten_dict(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            result[key_text] = child
            result.update(flatten_dict(child, key_text))
    elif isinstance(value, list):
        for child in value:
            result.update(flatten_dict(child, prefix))
    return result


def stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def classify_status(status_text: str | None, scheduled_departure: str | None, estimated_departure: str | None) -> str:
    text = (status_text or "").lower()
    if "cancel" in text or "取消" in text:
        return "cancelled"
    if "delay" in text or "延誤" in text:
        return "delayed"
    if scheduled_departure and estimated_departure and time_part(scheduled_departure) != time_part(estimated_departure):
        return "time_changed"
    if "depart" in text or "landed" in text or "arrived" in text:
        return text.replace(" ", "_")
    return "scheduled"


def time_part(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value[: len(fmt)], fmt).strftime("%H:%M")
        except ValueError:
            pass
    if len(value) >= 5 and value[-5:-2] == ":":
        return value[-5:]
    return value


def handle_success(state: dict[str, Any], status: dict[str, Any]) -> None:
    new_signature = status_signature(status)
    old_signature = state.get("last_signature")
    old_status = state.get("last_status")
    if not state.get("startup_sent"):
        send_telegram(f"AK1511 監視器已上線，目前狀態:{status_display(status)}")
        state["startup_sent"] = True
    elif old_signature and old_signature != new_signature:
        send_telegram(f"⚠️ {FLIGHT_NO}({FLIGHT_DATE})狀態變更:{status_display(old_status)} → {status_display(status)}")
    state["last_signature"] = new_signature
    state["last_status"] = status
    state["fail_count"] = 0
    state["last_failure_alert_count"] = 0
    save_state(state)


def handle_failure(state: dict[str, Any], exc: Exception) -> None:
    fail_count = int(state.get("fail_count", 0)) + 1
    state["fail_count"] = fail_count
    state["last_error"] = str(exc)
    state["last_error_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    last_alert_count = int(state.get("last_failure_alert_count", 0))
    if fail_count >= FAIL_ALERT_THRESHOLD and last_alert_count != fail_count:
        send_telegram(f"⚠️ AK1511({FLIGHT_DATE})監視器故障,請自行查航班。連續失敗 {fail_count} 次。錯誤:{exc}")
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
    return str(status.get("status_text") or normalized)


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
        return {"corrupt_state_replaced_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"}


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    tmp_path = f"{STATE_PATH}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp_path, STATE_PATH)


def compact(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WatchError as error:
        print(f"flight_watch error: {error}", file=sys.stderr)
        time.sleep(0.2)
        raise SystemExit(2)
