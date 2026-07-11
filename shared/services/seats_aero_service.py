from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models.point_wallet import AwardQuote, AwardSnapshot, AwardWatch, ExpiryAlert, HotelVoucher, PointAccount, PointProgram
from shared.services.point_wallet_service import PointWalletError, PointWalletNotFoundError, get_portfolio_summary


SEATS_AERO_SEARCH_URL = "https://seats.aero/partnerapi/search"
SEATS_AERO_TRIPS_URL = "https://seats.aero/partnerapi/trips"
EXPIRY_THRESHOLDS = (90, 60, 30, 7)
CABIN_PREFIX = {
    "economy": "Y",
    "premium": "W",
    "premium_economy": "W",
    "business": "J",
    "first": "F",
}


class SeatsAeroError(PointWalletError):
    pass


@dataclass(frozen=True)
class SeatsAeroFetchResult:
    snapshot: AwardSnapshot
    created: bool


class SeatsAeroClient:
    def __init__(self, *, api_key: str | None = None, base_url: str = SEATS_AERO_SEARCH_URL, timeout_seconds: int = 25) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("SEATS_AERO_API_KEY")
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def cached_search(
        self,
        *,
        origin: str,
        destination: str,
        cabin: str,
        start_date: date | None = None,
        end_date: date | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise SeatsAeroError("SEATS_AERO_API_KEY is required for seats.aero fetch")
        params: dict[str, str] = {
            "origin_airport": origin.upper(),
            "destination_airport": destination.upper(),
            "cabins": normalize_cabin(cabin),
            "take": "100",
        }
        if start_date is not None:
            params["start_date"] = start_date.isoformat()
        if end_date is not None:
            params["end_date"] = end_date.isoformat()
        if source:
            params["sources"] = seats_source_slug(source)
        request = Request(
            f"{self.base_url}?{urlencode(params)}",
            headers={
                "Accept": "application/json",
                "Partner-Authorization": self.api_key,
                "User-Agent": "PhiStyle-Point-Wallet/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise SeatsAeroError(f"seats.aero HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SeatsAeroError(f"seats.aero network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SeatsAeroError("seats.aero returned non-JSON response") from exc

    def get_trips(self, *, availability_id: str, include_filtered: bool = True) -> dict[str, Any]:
        if not self.api_key:
            raise SeatsAeroError("SEATS_AERO_API_KEY is required for seats.aero fetch")
        value = availability_id.strip()
        if not value:
            raise SeatsAeroError("availability_id is required for seats.aero trips fetch")
        request = Request(
            f"{SEATS_AERO_TRIPS_URL}/{value}?{urlencode({'include_filtered': str(include_filtered).lower()})}",
            headers={
                "Accept": "application/json",
                "Partner-Authorization": self.api_key,
                "User-Agent": "PhiStyle-Point-Wallet/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise SeatsAeroError(f"seats.aero trips HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SeatsAeroError(f"seats.aero trips network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SeatsAeroError("seats.aero trips returned non-JSON response") from exc


def create_award_watch(
    session: Session,
    *,
    origin: str,
    destination: str,
    cabin: str,
    start_date: date | None = None,
    end_date: date | None = None,
    program_id: int | None = None,
    active: bool = True,
    note: str | None = None,
) -> AwardWatch:
    if program_id is not None and session.get(PointProgram, program_id) is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    row = AwardWatch(
        origin=airport_code(origin),
        destination=airport_code(destination),
        cabin=normalize_cabin(cabin),
        start_date=start_date,
        end_date=end_date,
        program_id=program_id,
        active=active,
        note=note,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(row)
    session.commit()
    return row


def list_award_watches(session: Session) -> list[AwardWatch]:
    return list(
        session.scalars(
            select(AwardWatch)
            .where((AwardWatch.note.is_(None)) | (~AwardWatch.note.startswith("seats_trip_detail:")))
            .order_by(AwardWatch.active.desc(), AwardWatch.id.desc())
        )
    )


def update_award_watch(
    session: Session,
    *,
    watch_id: int,
    origin: str,
    destination: str,
    cabin: str,
    start_date: date | None = None,
    end_date: date | None = None,
    program_id: int | None = None,
    active: bool = True,
    note: str | None = None,
) -> AwardWatch:
    row = session.get(AwardWatch, watch_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown award_watch_id: {watch_id}")
    if program_id is not None and session.get(PointProgram, program_id) is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    row.origin = airport_code(origin)
    row.destination = airport_code(destination)
    row.cabin = normalize_cabin(cabin)
    row.start_date = start_date
    row.end_date = end_date
    row.program_id = program_id
    row.active = active
    row.note = note
    row.updated_at = datetime.now(UTC)
    session.commit()
    return row


def delete_award_watch(session: Session, *, watch_id: int) -> None:
    row = session.get(AwardWatch, watch_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown award_watch_id: {watch_id}")
    session.delete(row)
    session.commit()


def list_award_snapshots(session: Session, *, watch_id: int | None = None) -> list[AwardSnapshot]:
    statement = (
        select(AwardSnapshot)
        .join(AwardWatch, AwardSnapshot.watch_id == AwardWatch.id)
        .where((AwardWatch.note.is_(None)) | (~AwardWatch.note.startswith("seats_trip_detail:")))
        .order_by(AwardSnapshot.seen_date.desc(), AwardSnapshot.id.desc())
    )
    if watch_id is not None:
        statement = statement.where(AwardSnapshot.watch_id == watch_id)
    return list(session.scalars(statement))


def fetch_award_watch(
    session: Session,
    *,
    watch_id: int,
    client: SeatsAeroClient | None = None,
    seen_date: date | None = None,
) -> SeatsAeroFetchResult:
    watch = session.get(AwardWatch, watch_id)
    if watch is None:
        raise SeatsAeroError(f"Unknown watch_id: {watch_id}")
    if not watch.active:
        raise SeatsAeroError(f"watch_id {watch_id} is inactive")
    seen_date = seen_date or date.today()
    existing = session.scalar(select(AwardSnapshot).where(AwardSnapshot.watch_id == watch_id, AwardSnapshot.seen_date == seen_date))
    if existing is not None:
        return SeatsAeroFetchResult(snapshot=existing, created=False)
    source_name = watch.program.name if watch.program is not None else None
    payload = (client or SeatsAeroClient()).cached_search(
        origin=watch.origin,
        destination=watch.destination,
        cabin=watch.cabin,
        start_date=watch.start_date,
        end_date=watch.end_date,
        source=source_name,
    )
    normalized = normalize_cached_search_payload(payload, cabin=watch.cabin)
    row = AwardSnapshot(
        watch_id=watch.id,
        seen_date=seen_date,
        status="success",
        result_count=len(normalized),
        normalized_json=json.dumps(normalized, ensure_ascii=False, sort_keys=True),
        raw_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing_after_race = session.scalar(
            select(AwardSnapshot).where(AwardSnapshot.watch_id == watch_id, AwardSnapshot.seen_date == seen_date)
        )
        if existing_after_race is not None:
            return SeatsAeroFetchResult(snapshot=existing_after_race, created=False)
        raise
    return SeatsAeroFetchResult(snapshot=row, created=True)


def fetch_active_award_watches(
    session: Session,
    *,
    client: SeatsAeroClient | None = None,
    seen_date: date | None = None,
) -> list[SeatsAeroFetchResult]:
    rows = list(session.scalars(select(AwardWatch).where(AwardWatch.active.is_(True)).order_by(AwardWatch.id)))
    return [fetch_award_watch(session, watch_id=row.id, client=client, seen_date=seen_date) for row in rows]


def promote_snapshot_to_award_quote(session: Session, *, snapshot_id: int, item_index: int = 0) -> AwardQuote:
    snapshot = session.get(AwardSnapshot, snapshot_id)
    if snapshot is None:
        raise PointWalletNotFoundError(f"Unknown award_snapshot_id: {snapshot_id}")
    try:
        items = json.loads(snapshot.normalized_json)
    except json.JSONDecodeError as exc:
        raise SeatsAeroError("Snapshot normalized_json is invalid") from exc
    if not isinstance(items, list) or not items:
        raise SeatsAeroError("Snapshot has no availability to promote")
    if item_index < 0 or item_index >= len(items):
        raise SeatsAeroError("Snapshot item_index is out of range")
    item = items[item_index]
    if not isinstance(item, dict):
        raise SeatsAeroError("Snapshot item is invalid")
    program = _program_for_snapshot_item(session, snapshot.watch, item)
    row = AwardQuote(
        origin=str(item.get("origin") or snapshot.watch.origin),
        destination=str(item.get("destination") or snapshot.watch.destination),
        travel_date=_parse_date(item.get("travel_date")),
        cabin=str(item.get("cabin") or snapshot.watch.cabin),
        pax=1,
        program_id=program.id,
        miles_required=Decimal(str(item.get("miles_required") or "0")),
        taxes_amount=None,
        taxes_currency=None,
        cash_price_twd=None,
        source="seats_aero",
        created_at=datetime.now(UTC),
    )
    if row.miles_required <= 0:
        raise SeatsAeroError("Snapshot item has no positive mileage cost")
    session.add(row)
    session.commit()
    return row


def scan_expiry_alerts(session: Session, *, today: date | None = None) -> list[ExpiryAlert]:
    today = today or date.today()
    summary = get_portfolio_summary(session, today=today)
    created: list[ExpiryAlert] = []
    for account_summary in summary["accounts"]:
        expires_at = account_summary.expires_at
        if expires_at is None or account_summary.balance <= 0:
            continue
        days_left = (expires_at - today).days
        if days_left not in EXPIRY_THRESHOLDS:
            continue
        existing = session.scalar(
            select(ExpiryAlert).where(
                ExpiryAlert.account_id == account_summary.account_id,
                ExpiryAlert.threshold_days == days_left,
                ExpiryAlert.expires_at == expires_at,
                ExpiryAlert.checked_on == today,
            )
        )
        if existing is not None:
            continue
        row = ExpiryAlert(
            account_id=account_summary.account_id,
            voucher_id=None,
            threshold_days=days_left,
            expires_at=expires_at,
            checked_on=today,
            balance=account_summary.balance,
            status="open",
            message=expiry_message(account_summary.program_name, days_left, expires_at),
            created_at=datetime.now(UTC),
        )
        session.add(row)
        created.append(row)
    vouchers = list(session.scalars(select(HotelVoucher).where(HotelVoucher.status == "active").order_by(HotelVoucher.expires_at, HotelVoucher.id)))
    for voucher in vouchers:
        days_left = (voucher.expires_at - today).days
        if days_left < 0:
            voucher.status = "expired"
            continue
        if days_left not in EXPIRY_THRESHOLDS:
            continue
        existing = session.scalar(
            select(ExpiryAlert).where(
                ExpiryAlert.voucher_id == voucher.id,
                ExpiryAlert.threshold_days == days_left,
                ExpiryAlert.expires_at == voucher.expires_at,
                ExpiryAlert.checked_on == today,
            )
        )
        if existing is not None:
            continue
        row = ExpiryAlert(
            account_id=None,
            voucher_id=voucher.id,
            threshold_days=days_left,
            expires_at=voucher.expires_at,
            checked_on=today,
            balance=voucher.face_value_points,
            status="open",
            message=voucher_expiry_message(voucher, days_left),
            created_at=datetime.now(UTC),
        )
        session.add(row)
        created.append(row)
    session.commit()
    return created


def list_expiry_alerts(session: Session, *, status: str | None = None) -> list[ExpiryAlert]:
    statement = select(ExpiryAlert).order_by(ExpiryAlert.checked_on.desc(), ExpiryAlert.threshold_days, ExpiryAlert.id.desc())
    if status is not None:
        statement = statement.where(ExpiryAlert.status == status)
    return list(session.scalars(statement))


def normalize_cached_search_payload(payload: dict[str, Any], *, cabin: str) -> list[dict[str, Any]]:
    prefix = cabin_prefix(cabin)
    results = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if not bool(item.get(f"{prefix}Available")):
            continue
        route = item.get("Route") if isinstance(item.get("Route"), dict) else {}
        miles = _parse_decimal(item.get(f"{prefix}MileageCost"))
        if miles is None or miles <= 0:
            continue
        normalized.append(
            {
                "seats_aero_id": _string_or_none(item.get("ID")),
                "origin": _string_or_none(route.get("OriginAirport")),
                "destination": _string_or_none(route.get("DestinationAirport")),
                "travel_date": _string_or_none(item.get("Date")) or _string_or_none(item.get("ParsedDate")),
                "cabin": normalize_cabin(cabin),
                "program_source": _string_or_none(item.get("Source")) or _string_or_none(route.get("Source")),
                "miles_required": str(miles),
                "remaining_seats": _parse_int(item.get(f"{prefix}RemainingSeats")),
                "taxes": _normalize_tax_amount(item.get(f"{prefix}TotalTaxes"), item.get("TaxesCurrency")),
                "airlines": _string_or_none(item.get(f"{prefix}Airlines")),
                "direct": bool(item.get(f"{prefix}Direct")),
                "updated_at": _string_or_none(item.get("UpdatedAt")),
            }
        )
    return normalized


def airport_code(value: str) -> str:
    text = value.strip().upper()
    if len(text) != 3 or not text.isalpha():
        raise SeatsAeroError("Airport code must be a 3-letter IATA code")
    return text


def normalize_cabin(value: str) -> str:
    text = value.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "經濟": "economy",
        "經濟艙": "economy",
        "豪經": "premium",
        "豪華經濟艙": "premium",
        "商務": "business",
        "商務艙": "business",
        "頭等": "first",
        "頭等艙": "first",
    }
    text = aliases.get(text, text)
    if text not in CABIN_PREFIX:
        raise SeatsAeroError("Cabin must be economy, premium, business, or first")
    return "premium" if text == "premium_economy" else text


def cabin_prefix(value: str) -> str:
    return CABIN_PREFIX[normalize_cabin(value)]


def seats_source_slug(value: str) -> str:
    return value.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def expiry_message(program_name: str, days_left: int, expires_at: date) -> str:
    actions = {
        90: "檢查是否能透過小額活動延長效期，並標記可用兌換方向。",
        60: "確認近期旅遊需求；若沒有需求，評估轉點或低成本保點。",
        30: "優先處理：建立兌換候選或安排保點動作。",
        7: "最後提醒：今天就決定使用、保點或接受過期。",
    }
    return f"{program_name} 點數將於 {expires_at.isoformat()} 到期，剩 {days_left} 天。建議：{actions[days_left]}"


def voucher_expiry_message(voucher: HotelVoucher, days_left: int) -> str:
    face_k = (voucher.face_value_points / Decimal("1000")).to_integral_value()
    return f"🏨 {voucher.owner} 的 {voucher.program.name} 免房券({face_k}K)將於 {days_left} 天後到期"


def _program_for_snapshot_item(session: Session, watch: AwardWatch, item: dict[str, Any]) -> PointProgram:
    if watch.program_id is not None:
        program = session.get(PointProgram, watch.program_id)
        if program is not None:
            return program
    source = _string_or_none(item.get("program_source"))
    if source:
        source_slug = seats_source_slug(source)
        programs = list(session.scalars(select(PointProgram)))
        for program in programs:
            if seats_source_slug(program.name) == source_slug:
                return program
    raise SeatsAeroError("找不到可對應的點數計畫；請先建立或選擇 watch 的計畫。")


def _parse_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_trip_buckets(payload: dict[str, Any], *, cabin: str) -> list[dict[str, Any]]:
    requested_cabin = normalize_cabin(cabin)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            row_cabin = normalize_cabin(str(row.get("Cabin") or ""))
        except SeatsAeroError:
            continue
        if row_cabin != requested_cabin:
            continue
        miles = _parse_decimal(row.get("MileageCost"))
        seats = _parse_int(row.get("RemainingSeats"))
        if miles is None or miles <= 0 or seats is None or seats < 1:
            continue
        normalized.append(
            {
                "trip_id": _string_or_none(row.get("ID")),
                "cabin": requested_cabin,
                "miles_required": str(miles),
                "remaining_seats": seats,
                "taxes": _normalize_tax_amount(row.get("TotalTaxes"), row.get("TaxesCurrency")),
                "departs_at": _string_or_none(row.get("DepartsAt")),
                "arrives_at": _string_or_none(row.get("ArrivesAt")),
                "flight_numbers": _string_or_none(row.get("FlightNumbers")),
            }
        )
    return sorted(normalized, key=lambda row: (Decimal(row["miles_required"]), -int(row["remaining_seats"])))


def _normalize_tax_amount(value: Any, currency: Any) -> str | None:
    if value is None or not currency:
        return None
    amount = _parse_decimal(value)
    if amount is None:
        return None
    major_units = amount / Decimal("100")
    return f"{major_units.quantize(Decimal('0.01'))} {str(currency).strip().upper()}"


def _parse_date(value: Any) -> date | None:
    text = _string_or_none(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
