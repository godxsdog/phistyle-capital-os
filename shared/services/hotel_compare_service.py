from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.point_wallet import CostLot, HotelStayQuote, HotelVoucher, LedgerTransaction, PointAccount, PointProgram
from shared.services.point_wallet_service import PointWalletError, PointWalletNotFoundError


@dataclass(frozen=True)
class LotSnapshot:
    id: int
    remaining_quantity: Decimal
    total_cost_twd: Decimal
    acquired_at: date


@dataclass(frozen=True)
class PointCost:
    cost_twd: Decimal
    available: bool
    partial_cost_basis: bool
    lots_consumed: tuple[dict[str, str | int], ...]
    note: str | None = None


def create_hotel_stay_quote(
    session: Session,
    *,
    owner: str,
    hotel_name: str,
    stay_date: date,
    nights: int,
    program_id: int,
    cash_price_twd: Decimal,
    points_price_per_night: Decimal,
    taxes_note: str | None = None,
    topup_allowed: bool = False,
    topup_points: Decimal | None = None,
) -> HotelStayQuote:
    owner = _normalize_owner(owner)
    if session.get(PointProgram, program_id) is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    if not hotel_name.strip():
        raise PointWalletError("hotel_name is required")
    if nights < 1:
        raise PointWalletError("nights must be at least 1")
    if cash_price_twd <= 0:
        raise PointWalletError("cash_price_twd must be positive")
    if points_price_per_night <= 0:
        raise PointWalletError("points_price_per_night must be positive")
    if topup_points is not None and topup_points < 0:
        raise PointWalletError("topup_points must be zero or positive")
    row = HotelStayQuote(
        owner=owner,
        hotel_name=hotel_name.strip(),
        stay_date=stay_date,
        nights=nights,
        program_id=program_id,
        cash_price_twd=cash_price_twd,
        points_price_per_night=points_price_per_night,
        taxes_note=taxes_note,
        topup_allowed=topup_allowed,
        topup_points=topup_points,
    )
    session.add(row)
    session.commit()
    return row


def list_hotel_stay_quotes(session: Session) -> list[HotelStayQuote]:
    return list(session.scalars(select(HotelStayQuote).order_by(HotelStayQuote.created_at.desc(), HotelStayQuote.id.desc())))


def get_hotel_stay_quote(session: Session, quote_id: int) -> HotelStayQuote:
    row = session.get(HotelStayQuote, quote_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown hotel_stay_quote_id: {quote_id}")
    return row


def evaluate_hotel_stay_quote(session: Session, quote_id: int) -> dict[str, Any]:
    quote = get_hotel_stay_quote(session, quote_id)
    total_points = quote.points_price_per_night * Decimal(quote.nights)
    cpp = (quote.cash_price_twd / total_points).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    balance = _owner_balance(session, owner=quote.owner, program_id=quote.program_id)
    lots = _owner_lots(session, owner=quote.owner, program_id=quote.program_id)
    vouchers = _active_vouchers(session, owner=quote.owner, program_id=quote.program_id)
    options = [
        _cash_option(quote),
        _pure_points_option(quote, total_points=total_points, balance=balance, lots=lots),
        _voucher_option(quote, balance=balance, lots=lots, vouchers=vouchers),
        _voucher_topup_option(quote, balance=balance, lots=lots, vouchers=vouchers),
    ]
    ranked = _rank_options(options)
    return {
        "quote": _quote_payload(quote),
        "cpp": str(cpp),
        "total_points": str(_points(total_points)),
        "options": ranked,
        "notes": ["機會成本與住宿價值基準尚未自動化，請自行心算。"],
    }


def _cash_option(quote: HotelStayQuote) -> dict[str, Any]:
    return {
        "method": "cash",
        "label": "現金",
        "available": True,
        "cash_cost_twd": str(_money(quote.cash_price_twd)),
        "rank": None,
        "notes": ["直接支付現金房價。"],
        "voucher_ids": [],
        "nights_with_voucher": 0,
        "nights_with_points": 0,
        "points_consumed": "0.00",
    }


def _pure_points_option(quote: HotelStayQuote, *, total_points: Decimal, balance: Decimal, lots: tuple[LotSnapshot, ...]) -> dict[str, Any]:
    cost = _point_cost(required=total_points, balance=balance, lots=lots)
    notes = ["純點數支付。"]
    if not cost.available:
        notes.append(cost.note or "點數不足")
    if cost.partial_cost_basis:
        notes.append("部分無成本基礎")
    return {
        "method": "points",
        "label": "純點數",
        "available": cost.available,
        "cash_cost_twd": str(_money(cost.cost_twd)) if cost.available else None,
        "rank": None,
        "notes": notes,
        "voucher_ids": [],
        "nights_with_voucher": 0,
        "nights_with_points": quote.nights,
        "points_consumed": str(_points(total_points)),
        "lots_consumed": list(cost.lots_consumed),
    }


def _voucher_option(quote: HotelStayQuote, *, balance: Decimal, lots: tuple[LotSnapshot, ...], vouchers: tuple[HotelVoucher, ...]) -> dict[str, Any]:
    eligible = [voucher for voucher in vouchers if voucher.face_value_points >= quote.points_price_per_night]
    selected = eligible[: quote.nights]
    point_nights = quote.nights - len(selected)
    points_required = quote.points_price_per_night * Decimal(point_nights)
    cost = _point_cost(required=points_required, balance=balance, lots=lots)
    available = bool(selected) and cost.available
    notes = [_voucher_note(selected), f"{len(selected)} 晚用券 + {point_nights} 晚點數"]
    if not selected:
        notes.append("沒有可覆蓋每晚點數價的 active 免房券")
    if not cost.available:
        notes.append(cost.note or "點數不足")
    if cost.partial_cost_basis:
        notes.append("部分無成本基礎")
    return {
        "method": "voucher",
        "label": "免房券",
        "available": available,
        "cash_cost_twd": str(_money(cost.cost_twd)) if available else None,
        "rank": None,
        "notes": [note for note in notes if note],
        "voucher_ids": [voucher.id for voucher in selected],
        "nights_with_voucher": len(selected),
        "nights_with_points": point_nights,
        "points_consumed": str(_points(points_required)),
        "lots_consumed": list(cost.lots_consumed),
    }


def _voucher_topup_option(quote: HotelStayQuote, *, balance: Decimal, lots: tuple[LotSnapshot, ...], vouchers: tuple[HotelVoucher, ...]) -> dict[str, Any]:
    if not quote.topup_allowed:
        return _unavailable_topup("券+補點", "本 quote 未允許補點。")
    limit = quote.topup_points or Decimal("0")
    eligible = [
        voucher
        for voucher in vouchers
        if voucher.face_value_points < quote.points_price_per_night
        and quote.points_price_per_night - voucher.face_value_points <= limit
    ]
    eligible = sorted(eligible, key=lambda voucher: (voucher.expires_at, quote.points_price_per_night - voucher.face_value_points, voucher.id))
    selected = eligible[: quote.nights]
    point_nights = quote.nights - len(selected)
    topup_required = sum((quote.points_price_per_night - voucher.face_value_points for voucher in selected), Decimal("0"))
    points_required = topup_required + (quote.points_price_per_night * Decimal(point_nights))
    cost = _point_cost(required=points_required, balance=balance, lots=lots)
    available = bool(selected) and cost.available
    notes = [_voucher_note(selected), f"{len(selected)} 晚券+補點 + {point_nights} 晚點數"]
    if not selected:
        notes.append("沒有符合補點上限的 active 免房券")
    if not cost.available:
        notes.append(cost.note or "點數不足")
    if cost.partial_cost_basis:
        notes.append("部分無成本基礎")
    return {
        "method": "voucher_topup",
        "label": "券+補點",
        "available": available,
        "cash_cost_twd": str(_money(cost.cost_twd)) if available else None,
        "rank": None,
        "notes": [note for note in notes if note],
        "voucher_ids": [voucher.id for voucher in selected],
        "nights_with_voucher": len(selected),
        "nights_with_points": point_nights,
        "points_consumed": str(_points(points_required)),
        "lots_consumed": list(cost.lots_consumed),
    }


def _unavailable_topup(label: str, note: str) -> dict[str, Any]:
    return {
        "method": "voucher_topup",
        "label": label,
        "available": False,
        "cash_cost_twd": None,
        "rank": None,
        "notes": [note],
        "voucher_ids": [],
        "nights_with_voucher": 0,
        "nights_with_points": 0,
        "points_consumed": "0.00",
        "lots_consumed": [],
    }


def _rank_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        [option for option in options if option["available"]],
        key=lambda option: (Decimal(str(option["cash_cost_twd"])), option["method"]),
    )
    ranks = {id(option): index + 1 for index, option in enumerate(ranked)}
    for option in options:
        option["rank"] = ranks.get(id(option))
    return sorted(options, key=lambda option: (option["rank"] is None, option["rank"] or 999, option["method"]))


def _point_cost(*, required: Decimal, balance: Decimal, lots: tuple[LotSnapshot, ...]) -> PointCost:
    if required <= 0:
        return PointCost(cost_twd=Decimal("0"), available=True, partial_cost_basis=False, lots_consumed=())
    if balance < required:
        return PointCost(cost_twd=Decimal("0"), available=False, partial_cost_basis=False, lots_consumed=(), note="點數不足")
    remaining = required
    cost = Decimal("0")
    consumed: list[dict[str, str | int]] = []
    for lot in sorted(lots, key=lambda item: (item.acquired_at, item.id)):
        if remaining <= 0:
            break
        take = min(lot.remaining_quantity, remaining)
        if take <= 0:
            continue
        lot_cost = (lot.total_cost_twd * take / lot.remaining_quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cost += lot_cost
        consumed.append({"lot_id": lot.id, "qty": str(_points(take)), "cost_twd": str(_money(lot_cost))})
        remaining -= take
    return PointCost(
        cost_twd=_money(cost),
        available=True,
        partial_cost_basis=remaining > 0,
        lots_consumed=tuple(consumed),
    )


def _owner_balance(session: Session, *, owner: str, program_id: int) -> Decimal:
    account_ids = _owner_account_ids(session, owner=owner, program_id=program_id)
    if not account_ids:
        return Decimal("0")
    return sum(session.scalars(select(LedgerTransaction.quantity).where(LedgerTransaction.account_id.in_(account_ids))), Decimal("0"))


def _owner_lots(session: Session, *, owner: str, program_id: int) -> tuple[LotSnapshot, ...]:
    account_ids = _owner_account_ids(session, owner=owner, program_id=program_id)
    if not account_ids:
        return ()
    return tuple(
        LotSnapshot(id=lot.id, remaining_quantity=lot.remaining_quantity, total_cost_twd=lot.total_cost_twd, acquired_at=lot.acquired_at)
        for lot in session.scalars(
            select(CostLot)
            .where(CostLot.account_id.in_(account_ids), CostLot.remaining_quantity > 0)
            .order_by(CostLot.acquired_at, CostLot.id)
        )
    )


def _owner_account_ids(session: Session, *, owner: str, program_id: int) -> list[int]:
    return list(
        session.scalars(
            select(PointAccount.id).where(PointAccount.owner == _normalize_owner(owner), PointAccount.program_id == program_id)
        )
    )


def _active_vouchers(session: Session, *, owner: str, program_id: int) -> tuple[HotelVoucher, ...]:
    return tuple(
        session.scalars(
            select(HotelVoucher)
            .where(HotelVoucher.owner == _normalize_owner(owner), HotelVoucher.program_id == program_id, HotelVoucher.status == "active")
            .order_by(HotelVoucher.expires_at, HotelVoucher.id)
        )
    )


def _voucher_note(vouchers: list[HotelVoucher]) -> str | None:
    if not vouchers:
        return None
    parts = [
        f"消耗面額 {(voucher.face_value_points / Decimal('1000')).to_integral_value()}K 券(到期 {voucher.expires_at.isoformat()})"
        for voucher in vouchers
    ]
    return "；".join(parts)


def _quote_payload(quote: HotelStayQuote) -> dict[str, Any]:
    return {
        "id": quote.id,
        "owner": quote.owner,
        "hotel_name": quote.hotel_name,
        "stay_date": quote.stay_date.isoformat(),
        "nights": quote.nights,
        "program_id": quote.program_id,
        "program_name": quote.program.name,
        "cash_price_twd": str(quote.cash_price_twd),
        "points_price_per_night": str(quote.points_price_per_night),
        "taxes_note": quote.taxes_note,
        "topup_allowed": quote.topup_allowed,
        "topup_points": str(quote.topup_points) if quote.topup_points is not None else None,
        "created_at": quote.created_at.isoformat(),
    }


def _normalize_owner(owner: str) -> str:
    normalized = owner.strip().lower()
    if normalized == "kai":
        normalized = "kent"
    if normalized not in {"kent", "wife"}:
        raise PointWalletError("owner must be kent or wife")
    return normalized


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _points(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
