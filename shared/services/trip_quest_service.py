from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.point_wallet import AwardSnapshot, AwardWatch, PointProgram, QuestResult, TripQuest
from shared.services.point_wallet_service import PointWalletError, PointWalletNotFoundError
from shared.services.seats_aero_service import SeatsAeroClient, SeatsAeroError, airport_code, create_award_watch, fetch_award_watch, normalize_cabin, normalize_trip_buckets, seats_source_slug


DETAIL_VERIFICATION_LIMIT = 10


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
    verified: bool = False

    @property
    def total_miles(self) -> Decimal:
        return self.outbound_miles + self.return_miles


@dataclass(frozen=True)
class ChainAvailability:
    program: str
    travel_date: date
    segments: tuple[dict[str, Any], ...]
    verified: bool = False

    @property
    def total_miles(self) -> Decimal:
        return sum((Decimal(str(segment["miles_required"])) for segment in self.segments), Decimal("0"))

    @property
    def seats_min(self) -> int:
        return min(int(segment["remaining_seats"]) for segment in self.segments)


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
            TripQuest.kind == "round_trip",
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
            kind="round_trip",
            segments_json=None,
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
    coarse_pairs = pair_availability(outbound, returns, programs=normalized_programs, trip_days=trip_days, pax=pax)
    pairs = verify_pair_buckets(
        session,
        quest=quest,
        pairs=coarse_pairs,
        pax=pax,
        run_date=run_date,
        client=client or SeatsAeroClient(),
    )

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


def run_chain_quest(
    session: Session,
    *,
    segments: list[dict[str, str]],
    programs: list[str],
    window_start: date,
    window_end: date,
    cabin: str,
    pax: int = 1,
    run_date: date | None = None,
    client: SeatsAeroClient | None = None,
) -> TripQuestRun:
    normalized_segments = _normalize_segments(segments)
    if window_end < window_start:
        raise TripQuestError("日期窗結束日不可早於開始日")
    if pax < 1:
        raise TripQuestError("人數至少為 1 人")
    normalized_cabin = normalize_cabin(cabin)
    normalized_programs = _normalize_programs(session, programs)
    programs_json = json.dumps(normalized_programs, ensure_ascii=False, separators=(",", ":"))
    segments_json = json.dumps(normalized_segments, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    run_date = run_date or date.today()
    quest = session.scalar(
        select(TripQuest)
        .where(
            TripQuest.origin == normalized_segments[0]["origin"],
            TripQuest.destination == normalized_segments[-1]["destination"],
            TripQuest.programs == programs_json,
            TripQuest.window_start == window_start,
            TripQuest.window_end == window_end,
            TripQuest.trip_days == 1,
            TripQuest.cabin == normalized_cabin,
            TripQuest.pax == pax,
            TripQuest.kind == "chain",
            TripQuest.segments_json == segments_json,
        )
        .order_by(TripQuest.id)
    )
    if quest is None:
        quest = TripQuest(
            origin=normalized_segments[0]["origin"],
            destination=normalized_segments[-1]["destination"],
            programs=programs_json,
            window_start=window_start,
            window_end=window_end,
            trip_days=1,
            cabin=normalized_cabin,
            pax=pax,
            kind="chain",
            segments_json=segments_json,
            created_at=datetime.now(UTC),
        )
        session.add(quest)
        session.commit()
    existing = list_quest_results(session, quest_id=quest.id, run_date=run_date)
    if existing:
        return TripQuestRun(quest=quest, results=tuple(existing), created_results=0)
    segment_rows: list[list[dict[str, Any]]] = []
    for index, segment in enumerate(normalized_segments):
        snapshot = _fetch_chain_segment_snapshot(session, quest, index, segment, client, run_date)
        segment_rows.append(_snapshot_items(snapshot))
    coarse = pair_chain_availability(segment_rows, programs=normalized_programs, pax=pax)
    candidates = verify_chain_buckets(
        session,
        quest=quest,
        candidates=coarse,
        pax=pax,
        run_date=run_date,
        client=client or SeatsAeroClient(),
    )
    rows: list[QuestResult] = []
    for rank, candidate in enumerate(candidates, start=1):
        first = candidate.segments[0]
        last = candidate.segments[-1]
        refs = {
            "bucket_verified": candidate.verified,
            "segments": [
                {"availability_id": segment.get("availability_id"), "trip_id": segment.get("trip_id")}
                for segment in candidate.segments
            ],
        }
        row = QuestResult(
            trip_quest_id=quest.id,
            run_date=run_date,
            rank=rank,
            program=candidate.program,
            outbound_date=candidate.travel_date,
            return_date=candidate.travel_date,
            outbound_miles=Decimal(str(first["miles_required"])),
            return_miles=Decimal(str(last["miles_required"])),
            total_miles=candidate.total_miles,
            outbound_taxes=_optional_text(first.get("taxes")),
            return_taxes=_optional_text(last.get("taxes")),
            seats_min=candidate.seats_min,
            raw_refs=json.dumps(refs, ensure_ascii=False, sort_keys=True),
            segments_json=json.dumps(candidate.segments, ensure_ascii=False, sort_keys=True),
        )
        session.add(row)
        rows.append(row)
    session.commit()
    return TripQuestRun(quest=quest, results=tuple(rows), created_results=len(rows))


def pair_chain_availability(
    segment_rows: list[list[dict[str, Any]]],
    *,
    programs: list[str],
    pax: int,
) -> list[ChainAvailability]:
    allowed = {seats_source_slug(program) for program in programs}
    by_segment: list[dict[tuple[date, str], dict[str, Any]]] = []
    for rows in segment_rows:
        choices: dict[tuple[date, str], dict[str, Any]] = {}
        for row in rows:
            program = str(row.get("program_source") or "").strip()
            program_slug = seats_source_slug(program)
            seats = _required_seats(row.get("remaining_seats"))
            if program_slug not in allowed or seats < pax:
                continue
            travel_date = _required_date(row.get("travel_date"))
            key = (travel_date, program_slug)
            candidate = {
                "availability_id": row.get("seats_aero_id"),
                "origin": row.get("origin"),
                "destination": row.get("destination"),
                "date": travel_date.isoformat(),
                "program": program,
                "miles_required": str(_required_miles(row.get("miles_required"))),
                "remaining_seats": seats,
                "taxes": _optional_text(row.get("taxes")),
            }
            current = choices.get(key)
            if current is None or Decimal(candidate["miles_required"]) < Decimal(current["miles_required"]):
                choices[key] = candidate
        by_segment.append(choices)
    if not by_segment:
        return []
    common_keys = set(by_segment[0])
    for choices in by_segment[1:]:
        common_keys &= set(choices)
    candidates = [
        ChainAvailability(
            program=by_segment[0][key]["program"],
            travel_date=key[0],
            segments=tuple(choices[key] for choices in by_segment),
        )
        for key in common_keys
    ]
    return sorted(candidates, key=lambda candidate: (candidate.total_miles, candidate.travel_date))


def verify_chain_buckets(
    session: Session,
    *,
    quest: TripQuest,
    candidates: list[ChainAvailability],
    pax: int,
    run_date: date,
    client: SeatsAeroClient,
) -> list[ChainAvailability]:
    verified: list[ChainAvailability] = []
    unverified: list[ChainAvailability] = []
    local_cache: dict[str, list[dict[str, Any]] | None] = {}
    quest_segments = json.loads(quest.segments_json or "[]")
    for index, candidate in enumerate(candidates):
        if index >= DETAIL_VERIFICATION_LIMIT:
            unverified.append(candidate)
            continue
        detail_segments: list[dict[str, Any]] = []
        detail_failed = False
        ineligible = False
        for segment_index, coarse_segment in enumerate(candidate.segments):
            availability_id = str(coarse_segment.get("availability_id") or "")
            route = quest_segments[segment_index]
            buckets = _cached_detail_buckets(
                session,
                availability_id=availability_id,
                origin=route["origin"],
                destination=route["destination"],
                cabin=quest.cabin,
                travel_date=candidate.travel_date,
                run_date=run_date,
                client=client,
                local_cache=local_cache,
            )
            if buckets is None:
                detail_failed = True
                break
            bucket = _cheapest_eligible_bucket(buckets, pax)
            if bucket is None:
                ineligible = True
                break
            detail_segments.append(
                {
                    **coarse_segment,
                    "trip_id": bucket.get("trip_id"),
                    "miles_required": bucket["miles_required"],
                    "remaining_seats": bucket["remaining_seats"],
                    "taxes": bucket.get("taxes"),
                }
            )
        if ineligible:
            continue
        if detail_failed:
            unverified.append(candidate)
            continue
        verified.append(replace(candidate, segments=tuple(detail_segments), verified=True))
    return sorted(verified, key=lambda candidate: (candidate.total_miles, candidate.travel_date)) + sorted(
        unverified,
        key=lambda candidate: (candidate.total_miles, candidate.travel_date),
    )


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
                            "bucket_verified": False,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
            )
    return sorted(pairs, key=lambda pair: (pair.total_miles, pair.outbound_date))


def verify_pair_buckets(
    session: Session,
    *,
    quest: TripQuest,
    pairs: list[PairedAvailability],
    pax: int,
    run_date: date,
    client: SeatsAeroClient,
) -> list[PairedAvailability]:
    verified: list[PairedAvailability] = []
    unverified: list[PairedAvailability] = []
    local_cache: dict[str, list[dict[str, Any]] | None] = {}
    for index, pair in enumerate(pairs):
        if index >= DETAIL_VERIFICATION_LIMIT:
            unverified.append(_mark_pair_verification(pair, False))
            continue
        refs = _raw_ref_data(pair.raw_refs)
        outbound_id = str(refs.get("outbound") or "")
        return_id = str(refs.get("return") or "")
        if not outbound_id or not return_id:
            unverified.append(_mark_pair_verification(pair, False))
            continue
        outbound_buckets = _cached_detail_buckets(
            session,
            availability_id=outbound_id,
            origin=quest.origin,
            destination=quest.destination,
            cabin=quest.cabin,
            travel_date=pair.outbound_date,
            run_date=run_date,
            client=client,
            local_cache=local_cache,
        )
        return_buckets = _cached_detail_buckets(
            session,
            availability_id=return_id,
            origin=quest.destination,
            destination=quest.origin,
            cabin=quest.cabin,
            travel_date=pair.return_date,
            run_date=run_date,
            client=client,
            local_cache=local_cache,
        )
        if outbound_buckets is None or return_buckets is None:
            unverified.append(_mark_pair_verification(pair, False))
            continue
        outbound_bucket = _cheapest_eligible_bucket(outbound_buckets, pax)
        return_bucket = _cheapest_eligible_bucket(return_buckets, pax)
        if outbound_bucket is None or return_bucket is None:
            continue
        verified.append(
            replace(
                pair,
                outbound_miles=Decimal(outbound_bucket["miles_required"]),
                return_miles=Decimal(return_bucket["miles_required"]),
                outbound_taxes=_optional_text(outbound_bucket.get("taxes")),
                return_taxes=_optional_text(return_bucket.get("taxes")),
                seats_min=min(int(outbound_bucket["remaining_seats"]), int(return_bucket["remaining_seats"])),
                raw_refs=json.dumps(
                    {
                        **refs,
                        "bucket_verified": True,
                        "outbound_trip": outbound_bucket.get("trip_id"),
                        "return_trip": return_bucket.get("trip_id"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                verified=True,
            )
        )
    return sorted(verified, key=lambda pair: (pair.total_miles, pair.outbound_date)) + sorted(
        unverified,
        key=lambda pair: (pair.total_miles, pair.outbound_date),
    )


def _cached_detail_buckets(
    session: Session,
    *,
    availability_id: str,
    origin: str,
    destination: str,
    cabin: str,
    travel_date: date,
    run_date: date,
    client: SeatsAeroClient,
    local_cache: dict[str, list[dict[str, Any]] | None],
) -> list[dict[str, Any]] | None:
    if availability_id in local_cache:
        return local_cache[availability_id]
    normalized_cabin = normalize_cabin(cabin)
    note = f"seats_trip_detail:{normalized_cabin}:{availability_id}"
    watch = session.scalar(select(AwardWatch).where(AwardWatch.note == note).order_by(AwardWatch.id))
    if watch is None:
        watch = create_award_watch(
            session,
            origin=origin,
            destination=destination,
            cabin=cabin,
            start_date=travel_date,
            end_date=travel_date,
            active=False,
            note=note,
        )
    snapshot = session.scalar(
        select(AwardSnapshot).where(AwardSnapshot.watch_id == watch.id, AwardSnapshot.seen_date == run_date)
    )
    if snapshot is not None:
        buckets = _snapshot_items(snapshot)
        local_cache[availability_id] = buckets
        return buckets
    try:
        payload = client.get_trips(availability_id=availability_id, include_filtered=True)
    except SeatsAeroError:
        local_cache[availability_id] = None
        return None
    buckets = normalize_trip_buckets(payload, cabin=cabin)
    snapshot = AwardSnapshot(
        watch_id=watch.id,
        seen_date=run_date,
        status="detail_success",
        result_count=len(buckets),
        normalized_json=json.dumps(buckets, ensure_ascii=False, sort_keys=True),
        raw_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        created_at=datetime.now(UTC),
    )
    session.add(snapshot)
    session.commit()
    local_cache[availability_id] = buckets
    return buckets


def _cheapest_eligible_bucket(buckets: list[dict[str, Any]], pax: int) -> dict[str, Any] | None:
    eligible = [bucket for bucket in buckets if int(bucket.get("remaining_seats") or 0) >= pax]
    if not eligible:
        return None
    return min(eligible, key=lambda bucket: Decimal(str(bucket["miles_required"])))


def _mark_pair_verification(pair: PairedAvailability, verified: bool) -> PairedAvailability:
    refs = _raw_ref_data(pair.raw_refs)
    refs["bucket_verified"] = verified
    return replace(pair, raw_refs=json.dumps(refs, ensure_ascii=False, sort_keys=True), verified=verified)


def _raw_ref_data(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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


def _normalize_segments(segments: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(segments) < 2 or len(segments) > 3:
        raise TripQuestError("多段同日模式只支援 2 至 3 段")
    normalized: list[dict[str, str]] = []
    for segment in segments:
        origin = airport_code(str(segment.get("origin") or ""))
        destination = airport_code(str(segment.get("destination") or ""))
        if origin == destination:
            raise TripQuestError("每段出發地與目的地不可相同")
        normalized.append({"origin": origin, "destination": destination})
    return normalized


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


def _fetch_chain_segment_snapshot(
    session: Session,
    quest: TripQuest,
    index: int,
    segment: dict[str, str],
    client: SeatsAeroClient | None,
    run_date: date,
) -> AwardSnapshot:
    note = f"trip_quest:{quest.id}:segment:{index + 1}"
    watch = session.scalar(select(AwardWatch).where(AwardWatch.note == note).order_by(AwardWatch.id))
    if watch is None:
        watch = create_award_watch(
            session,
            origin=segment["origin"],
            destination=segment["destination"],
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
