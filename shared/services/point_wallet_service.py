from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models.point_wallet import (
    AwardAvailability,
    AwardWatch,
    LoyaltyProgram,
    PointBalance,
    TransferPartner,
    ValuationRate,
)


class PointWalletError(ValueError):
    pass


class PointWalletNotFoundError(PointWalletError):
    pass


@dataclass(frozen=True)
class PortfolioRow:
    program_id: int
    program_name: str
    balance: Decimal
    as_of: date
    expires_at: date | None
    twd_per_point: Decimal | None
    value_twd: Decimal | None


def create_loyalty_program(session: Session, *, name: str, kind: str, notes: str | None = None) -> LoyaltyProgram:
    program = LoyaltyProgram(name=_required(name, "name"), kind=_required(kind, "kind"), notes=notes)
    session.add(program)
    _commit(session)
    return program


def list_loyalty_programs(session: Session) -> list[LoyaltyProgram]:
    return list(session.scalars(select(LoyaltyProgram).order_by(LoyaltyProgram.name, LoyaltyProgram.id)))


def add_point_balance(
    session: Session,
    *,
    program_id: int,
    balance: Decimal,
    as_of: date,
    expires_at: date | None = None,
    note: str | None = None,
) -> PointBalance:
    _require_program(session, program_id)
    row = PointBalance(program_id=program_id, balance=balance, as_of=as_of, expires_at=expires_at, note=note)
    session.add(row)
    _commit(session)
    return row


def list_point_balances(session: Session) -> list[PointBalance]:
    return list(session.scalars(select(PointBalance).order_by(PointBalance.program_id, PointBalance.as_of, PointBalance.id)))


def add_valuation_rate(
    session: Session,
    *,
    program_id: int,
    twd_per_point: Decimal,
    effective_date: date,
    source: str | None = None,
) -> ValuationRate:
    _require_program(session, program_id)
    row = ValuationRate(
        program_id=program_id,
        twd_per_point=twd_per_point,
        effective_date=effective_date,
        source=source,
    )
    session.add(row)
    _commit(session)
    return row


def list_valuation_rates(session: Session) -> list[ValuationRate]:
    return list(session.scalars(select(ValuationRate).order_by(ValuationRate.program_id, ValuationRate.effective_date)))


def create_transfer_partner(
    session: Session,
    *,
    from_program_id: int,
    to_program_id: int,
    ratio_from: int,
    ratio_to: int,
    transfer_days: str | None = None,
    notes: str | None = None,
) -> TransferPartner:
    if ratio_from <= 0 or ratio_to <= 0:
        raise PointWalletError("Transfer ratios must be positive")
    _require_program(session, from_program_id)
    _require_program(session, to_program_id)
    row = TransferPartner(
        from_program_id=from_program_id,
        to_program_id=to_program_id,
        ratio_from=ratio_from,
        ratio_to=ratio_to,
        transfer_days=transfer_days,
        notes=notes,
    )
    session.add(row)
    _commit(session)
    return row


def list_transfer_partners(session: Session) -> list[TransferPartner]:
    return list(session.scalars(select(TransferPartner).order_by(TransferPartner.from_program_id, TransferPartner.to_program_id)))


def create_award_watch(
    session: Session,
    *,
    origin: str,
    destination: str,
    cabin: str,
    program_id: int | None = None,
    active: bool = True,
) -> AwardWatch:
    if program_id is not None:
        _require_program(session, program_id)
    row = AwardWatch(
        origin=_required(origin, "origin").upper(),
        destination=_required(destination, "destination").upper(),
        cabin=_required(cabin, "cabin").lower(),
        program_id=program_id,
        active=active,
    )
    session.add(row)
    _commit(session)
    return row


def list_award_watches(session: Session) -> list[AwardWatch]:
    return list(session.scalars(select(AwardWatch).order_by(AwardWatch.id)))


def add_award_availability(
    session: Session,
    *,
    watch_id: int,
    seen_date: date,
    flight_date: date,
    program: str,
    seats: int | None = None,
    miles_cost: Decimal | None = None,
    taxes_fees: str | None = None,
    source: str = "manual",
    raw: str | None = None,
) -> AwardAvailability:
    _require_watch(session, watch_id)
    if source not in {"manual", "seats_aero"}:
        raise PointWalletError("source must be manual or seats_aero")
    row = AwardAvailability(
        watch_id=watch_id,
        seen_date=seen_date,
        flight_date=flight_date,
        program=_required(program, "program"),
        seats=seats,
        miles_cost=miles_cost,
        taxes_fees=taxes_fees,
        source=source,
        raw=raw,
    )
    session.add(row)
    _commit(session)
    return row


def list_award_availability(session: Session, watch_id: int | None = None) -> list[AwardAvailability]:
    statement = select(AwardAvailability).order_by(AwardAvailability.seen_date, AwardAvailability.flight_date, AwardAvailability.id)
    if watch_id is not None:
        statement = statement.where(AwardAvailability.watch_id == watch_id)
    return list(session.scalars(statement))


def get_portfolio_summary(session: Session, *, today: date | None = None) -> dict[str, object]:
    today = today or date.today()
    balances = _latest_balances(session)
    rates = _latest_rates(session)
    programs = {program.id: program for program in list_loyalty_programs(session)}
    rows: list[PortfolioRow] = []
    total = Decimal("0")
    for program_id, balance in balances.items():
        rate = rates.get(program_id)
        value = balance.balance * rate.twd_per_point if rate else None
        if value is not None:
            total += value
        program = programs[program_id]
        rows.append(
            PortfolioRow(
                program_id=program_id,
                program_name=program.name,
                balance=balance.balance,
                as_of=balance.as_of,
                expires_at=balance.expires_at,
                twd_per_point=rate.twd_per_point if rate else None,
                value_twd=value,
            )
        )
    rows.sort(key=lambda row: row.program_name)
    expiry_cutoff = today + timedelta(days=90)
    expiring = [row for row in rows if row.expires_at is not None and today <= row.expires_at <= expiry_cutoff]
    return {"total_value_twd": total, "programs": rows, "expiring_soon": expiring}


def seed_default_valuation_programs(session: Session) -> None:
    defaults = [
        ("Chase Ultimate Rewards", "bank", Decimal("0.300000")),
        ("United MileagePlus", "airline", Decimal("0.280000")),
        ("Air Canada Aeroplan", "airline", Decimal("0.300000")),
    ]
    for name, kind, rate in defaults:
        existing = session.scalar(select(LoyaltyProgram).where(LoyaltyProgram.name == name))
        if existing is None:
            existing = LoyaltyProgram(name=name, kind=kind, notes="editable defaults, not market truth")
            session.add(existing)
            session.flush()
        has_rate = session.scalar(
            select(ValuationRate).where(
                ValuationRate.program_id == existing.id,
                ValuationRate.effective_date == date(2026, 1, 1),
            )
        )
        if has_rate is None:
            session.add(
                ValuationRate(
                    program_id=existing.id,
                    twd_per_point=rate,
                    effective_date=date(2026, 1, 1),
                    source="editable defaults, not market truth",
                )
            )
    _commit(session)


def _latest_balances(session: Session) -> dict[int, PointBalance]:
    rows = list_point_balances(session)
    latest: dict[int, PointBalance] = {}
    for row in rows:
        current = latest.get(row.program_id)
        if current is None or (row.as_of, row.id) >= (current.as_of, current.id):
            latest[row.program_id] = row
    return latest


def _latest_rates(session: Session) -> dict[int, ValuationRate]:
    rows = list_valuation_rates(session)
    latest: dict[int, ValuationRate] = {}
    for row in rows:
        current = latest.get(row.program_id)
        if current is None or (row.effective_date, row.id) >= (current.effective_date, current.id):
            latest[row.program_id] = row
    return latest


def _require_program(session: Session, program_id: int) -> LoyaltyProgram:
    program = session.get(LoyaltyProgram, program_id)
    if program is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    return program


def _require_watch(session: Session, watch_id: int) -> AwardWatch:
    watch = session.get(AwardWatch, watch_id)
    if watch is None:
        raise PointWalletNotFoundError(f"Unknown watch_id: {watch_id}")
    return watch


def _required(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise PointWalletError(f"{field} is required")
    return cleaned


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
