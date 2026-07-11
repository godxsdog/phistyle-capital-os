from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.point_wallet import AwardSnapshot, AwardWatch, PointProgram, QuestResult, TripQuest
from shared.services.point_wallet_service import PointWalletError, PointWalletNotFoundError
from shared.services.seats_aero_service import SeatsAeroClient, airport_code, create_award_watch, fetch_award_watch, normalize_cabin, seats_source_slug


class TripQuestError(PointWalletError):
    pass


@dataclass(frozen=True)
class TripQuestRun:
    quest: TripQuest
    results: tuple[QuestResult, ...]
    created_results: int


@dataclass(frozen=True)
class PairedAvailability:
    program: str
    outbound_date: date
    return_date: date
    outbound_miles: Decimal
    return_miles: Decimal
    outbound_taxes: str | None
    return_taxes: str | None
    seats_min: int
    raw_refs: str

    @property
    def total_miles(self) -> Decimal:
        return self.outbound_miles + self.return_miles


def run_trip_quest(
    session: Session,
    *,
    origin: str,
    destination: str,
    programs: list[str],
    window_start: date,
    window_end: date,
    trip_days: int,
    cabin: str,
    pax: int = 1,
    run_date: date | None = None,
    client: SeatsAeroClient | None = None,
) -> TripQuestRun:
    normalized_origin = airport_code(origin)
    normalized_destination = airport_code(destination)
    if normalized_origin == normalized_destination:
        raise TripQuestError("出發地與目的地不可相同")
    if window_end < window_start:
        raise TripQuestError("日期窗結束日不可早於開始日")
    if trip_days < 1:
        raise TripQuestError("旅程天數至少為 1 天")
    if pax < 1:
        raise TripQuestError("人數至少為 1 人")
    normalized_cabin = normalize_cabin(cabin)
    normalized_programs = _normalize_programs(session, programs)
    programs_json = json.dumps(normalized_programs, ensure_ascii=False, separators=(",", ":"))
    run_date = run_date or date.today()

    quest = session.scalar(
        select(TripQuest)
        .where(
            TripQuest.origin == normalized_origin,
            TripQuest.destination == normalized_destination,
            TripQuest.programs == programs_json,
            TripQuest.window_start == window_start,
            TripQuest.window_end == window_end,
            TripQuest.trip_days == trip_days,
            TripQuest.cabin == normalized_cabin,
            TripQuest.pax == pax,
        )
        .order_by(TripQuest.id)
    )
    if quest is None:
        quest = TripQuest(
            origin=normalized_origin,
            destination=normalized_destination,
            programs=programs_json,
            window_start=window_start,
            window_end=window_end,
            trip_days=trip_days,
            cabin=normalized_cabin,
            pax=pax,
            created_at=datetime.now(UTC),
        )
        session.add(quest)
        session.commit()

    existing = list_quest_results(session, quest_id=quest.id, run_date=run_date)
    if existing:
        return TripQuestRun(quest=quest, results=tuple(existing), created_results=0)

    outbound_snapshot = _fetch_direction_snapshot(session, quest, "outbound", client, run_date)
    return_snapshot = _fetch_direction_snapshot(session, quest, "return", client, run_date)
    outbound = _snapshot_items(outbound_snapshot)
    returns = _snapshot_items(return_snapshot)
    pairs = pair_availability(outbound, returns, programs=normalized_programs, trip_days=trip_days, pax=pax)

    rows: list[QuestResult] = []
    for rank, pair in enumerate(pairs, start=1):
        row = QuestResult(
            trip_quest_id=quest.id,
            run_date=run_date,
            rank=rank,
            program=pair.program,
            outbound_date=pair.outbound_date,
            return_date=pair.return_date,
            outbound_miles=pair.outbound_miles,
            return_miles=pair.return_miles,
            total_miles=pair.total_miles,
            outbound_taxes=pair.outbound_taxes,
            return_taxes=pair.return_taxes,
            seats_min=pair.seats_min,
            raw_refs=pair.raw_refs,
        )
        session.add(row)
        rows.append(row)
    session.commit()
    return TripQuestRun(quest=quest, results=tuple(rows), created_results=len(rows))


def pair_availability(
    outbound: Iterable[dict[str, Any]],
    returns: Iterable[dict[str, Any]],
    *,
    programs: list[str],
    trip_days: int,
    pax: int,
) -> list[PairedAvailability]:
    allowed = {seats_source_slug(program) for program in programs}
    pairs: list[PairedAvailability] = []
    for outbound_item in outbound:
        outbound_program = str(outbound_item.get("program_source") or "").strip()
        outbound_slug = seats_source_slug(outbound_program)
        outbound_date = _required_date(outbound_item.get("travel_date"))
        outbound_seats = _required_seats(outbound_item.get("remaining_seats"))
        if outbound_slug not in allowed or outbound_seats < pax:
            continue
        for return_item in returns:
            return_program = str(return_item.get("program_source") or "").strip()
            return_date = _required_date(return_item.get("travel_date"))
            return_seats = _required_seats(return_item.get("remaining_seats"))
            if seats_source_slug(return_program) != outbound_slug or return_seats < pax:
                continue
            earliest = outbound_date + timedelta(days=trip_days - 1)
            latest = outbound_date + timedelta(days=trip_days + 1)
            if not earliest <= return_date <= latest:
                continue
            pairs.append(
                PairedAvailability(
                    program=outbound_program,
                    outbound_date=outbound_date,
                    return_date=return_date,
                    outbound_miles=_required_miles(outbound_item.get("miles_required")),
                    return_miles=_required_miles(return_item.get("miles_required")),
                    outbound_taxes=_optional_text(outbound_item.get("taxes")),
                    return_taxes=_optional_text(return_item.get("taxes")),
                    seats_min=min(outbound_seats, return_seats),
                    raw_refs=json.dumps(
                        {
                            "outbound": outbound_item.get("seats_aero_id"),
                            "return": return_item.get("seats_aero_id"),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
            )
    return sorted(pairs, key=lambda pair: (pair.total_miles, pair.outbound_date))


def list_trip_quests(session: Session) -> list[TripQuest]:
    return list(session.scalars(select(TripQuest).order_by(TripQuest.created_at.desc(), TripQuest.id.desc())))


def get_trip_quest(session: Session, quest_id: int) -> TripQuest:
    quest = session.get(TripQuest, quest_id)
    if quest is None:
        raise PointWalletNotFoundError(f"Unknown trip_quest_id: {quest_id}")
    return quest


def list_quest_results(session: Session, *, quest_id: int, run_date: date | None = None) -> list[QuestResult]:
    statement = select(QuestResult).where(QuestResult.trip_quest_id == quest_id)
    if run_date is not None:
        statement = statement.where(QuestResult.run_date == run_date)
    return list(session.scalars(statement.order_by(QuestResult.run_date.desc(), QuestResult.rank)))


def get_quest_result(session: Session, result_id: int) -> QuestResult:
    row = session.get(QuestResult, result_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown quest_result_id: {result_id}")
    return row


def _normalize_programs(session: Session, programs: list[str]) -> list[str]:
    requested = {seats_source_slug(value) for value in programs if value.strip()}
    if not requested:
        raise TripQuestError("請至少選擇一個計畫")
    rows = list(session.scalars(select(PointProgram).order_by(PointProgram.name)))
    matched = [row.name for row in rows if seats_source_slug(row.name) in requested]
    missing = requested - {seats_source_slug(name) for name in matched}
    if missing:
        raise TripQuestError(f"找不到計畫：{', '.join(sorted(missing))}")
    return sorted(matched, key=seats_source_slug)


def _fetch_direction_snapshot(
    session: Session,
    quest: TripQuest,
    direction: str,
    client: SeatsAeroClient | None,
    run_date: date,
) -> AwardSnapshot:
    note = f"trip_quest:{quest.id}:{direction}"
    watch = session.scalar(select(AwardWatch).where(AwardWatch.note == note).order_by(AwardWatch.id))
    if watch is None:
        outbound = direction == "outbound"
        watch = create_award_watch(
            session,
            origin=quest.origin if outbound else quest.destination,
            destination=quest.destination if outbound else quest.origin,
            cabin=quest.cabin,
            start_date=quest.window_start,
            end_date=quest.window_end,
            note=note,
        )
    return fetch_award_watch(session, watch_id=watch.id, client=client, seen_date=run_date).snapshot


def _snapshot_items(snapshot: AwardSnapshot) -> list[dict[str, Any]]:
    try:
        value = json.loads(snapshot.normalized_json)
    except json.JSONDecodeError as exc:
        raise TripQuestError("旅程快照格式錯誤") from exc
    return value if isinstance(value, list) else []


def _required_date(value: Any) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise TripQuestError("seats.aero 結果缺少有效日期") from exc


def _required_miles(value: Any) -> Decimal:
    try:
        miles = Decimal(str(value))
    except Exception as exc:
        raise TripQuestError("seats.aero 結果缺少有效哩程") from exc
    if miles <= 0:
        raise TripQuestError("seats.aero 結果哩程必須大於零")
    return miles


def _required_seats(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TripQuestError("seats.aero 結果缺少剩餘座位") from exc


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
