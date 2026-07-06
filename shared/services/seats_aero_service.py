from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models.point_wallet import AwardAvailability, AwardWatch
from shared.services.point_wallet_service import PointWalletError


SEATS_AERO_SEARCH_URL = "https://seats.aero/partnerapi/search"


class SeatsAeroError(PointWalletError):
    pass


class SeatsAeroClient:
    def __init__(self, *, api_key: str | None = None, base_url: str = SEATS_AERO_SEARCH_URL) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("SEATS_AERO_API_KEY")
        self.base_url = base_url

    def cached_search(self, *, origin: str, destination: str, cabin: str, source: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise SeatsAeroError("SEATS_AERO_API_KEY is required for seats.aero fetch")
        params: dict[str, str] = {
            "origin_airport": origin,
            "destination_airport": destination,
            "cabins": cabin,
            "take": "100",
        }
        if source:
            params["sources"] = source
        request = Request(
            f"{self.base_url}?{urlencode(params)}",
            headers={"Partner-Authorization": self.api_key, "Accept": "application/json"},
            method="GET",
        )
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))


def fetch_award_watch(
    session: Session,
    *,
    watch_id: int,
    client: SeatsAeroClient | None = None,
    seen_date: date | None = None,
) -> dict[str, int]:
    watch = session.get(AwardWatch, watch_id)
    if watch is None:
        raise SeatsAeroError(f"Unknown watch_id: {watch_id}")
    if not watch.active:
        raise SeatsAeroError(f"watch_id {watch_id} is inactive")
    seen_date = seen_date or date.today()
    client = client or SeatsAeroClient()
    source_name = watch.program.name if watch.program is not None else None
    payload = client.cached_search(
        origin=watch.origin,
        destination=watch.destination,
        cabin=watch.cabin,
        source=source_name,
    )
    created = 0
    for item in _extract_results(payload):
        flight_date = _parse_date(item.get("date") or item.get("flight_date") or item.get("Date"))
        if flight_date is None:
            continue
        program = str(item.get("source") or item.get("program") or item.get("Source") or source_name or "unknown")
        exists = session.scalar(
            select(AwardAvailability).where(
                AwardAvailability.watch_id == watch.id,
                AwardAvailability.seen_date == seen_date,
                AwardAvailability.flight_date == flight_date,
                AwardAvailability.program == program,
                AwardAvailability.source == "seats_aero",
            )
        )
        if exists is not None:
            continue
        session.add(
            AwardAvailability(
                watch_id=watch.id,
                seen_date=seen_date,
                flight_date=flight_date,
                program=program,
                seats=_parse_int(item.get("seats") or item.get("SeatsAvailable")),
                miles_cost=_parse_decimal(item.get("mileage") or item.get("miles") or item.get("MileageCost")),
                taxes_fees=_string_or_none(item.get("taxes") or item.get("taxes_fees") or item.get("Taxes")),
                source="seats_aero",
                raw=json.dumps(item, ensure_ascii=False),
            )
        )
        created += 1
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    return {"created": created}


def _extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("data", "results", "availability"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if isinstance(payload.get("Data"), list):
        return [item for item in payload["Data"] if isinstance(item, dict)]
    return []


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
