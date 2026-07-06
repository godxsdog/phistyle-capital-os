from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models.point_wallet import (
    CostLot,
    LedgerTransaction,
    PointAccount,
    PointProgram,
    PurchaseOffer,
    TransferRule,
)
from shared.services.exchange_rate_service import get_twd_per_unit


VALID_OWNERS = {"kent", "wife"}
VALID_PROGRAM_KINDS = {"airline", "hotel", "bank", "other"}
VALID_TRANSACTION_KINDS = {"earn", "buy", "transfer_in", "transfer_out", "redeem", "expire", "adjustment"}


class PointWalletError(ValueError):
    pass


class PointWalletNotFoundError(PointWalletError):
    pass


@dataclass(frozen=True)
class AccountSummary:
    account_id: int
    owner: str
    program_id: int
    program_name: str
    program_kind: str
    balance: Decimal
    remaining_lot_quantity: Decimal
    real_cost_basis_twd: Decimal
    avg_cost_per_point_twd: Decimal | None
    market_value_twd: Decimal | None
    expires_at: date | None


def create_program(session: Session, *, name: str, kind: str, expiry_rule_note: str | None = None) -> PointProgram:
    kind = kind.strip().lower()
    if kind not in VALID_PROGRAM_KINDS:
        raise PointWalletError("kind must be airline, hotel, bank, or other")
    row = PointProgram(name=_required(name, "name"), kind=kind, expiry_rule_note=expiry_rule_note)
    session.add(row)
    _commit(session)
    return row


def get_or_create_program(
    session: Session,
    *,
    name: str,
    kind: str = "other",
    expiry_rule_note: str | None = None,
) -> PointProgram:
    existing = session.scalar(select(PointProgram).where(PointProgram.name == name))
    if existing is not None:
        return existing
    row = PointProgram(name=name, kind=kind if kind in VALID_PROGRAM_KINDS else "other", expiry_rule_note=expiry_rule_note)
    session.add(row)
    session.flush()
    return row


def list_programs(session: Session) -> list[PointProgram]:
    return list(session.scalars(select(PointProgram).order_by(PointProgram.name, PointProgram.id)))


def create_account(
    session: Session,
    *,
    owner: str,
    program_id: int,
    account_ref: str | None = None,
    status: str = "active",
    last_activity: date | None = None,
    notes: str | None = None,
) -> PointAccount:
    owner = _normalize_owner(owner)
    _require_program(session, program_id)
    row = PointAccount(
        owner=owner,
        program_id=program_id,
        account_ref=_mask_account_ref(account_ref),
        status=_required(status, "status"),
        last_activity=last_activity,
        notes=notes,
    )
    session.add(row)
    _commit(session)
    return row


def get_or_create_account(
    session: Session,
    *,
    owner: str,
    program: PointProgram,
    account_ref: str | None = None,
    status: str = "active",
    last_activity: date | None = None,
    notes: str | None = None,
) -> PointAccount:
    owner = _normalize_owner(owner)
    existing = session.scalar(
        select(PointAccount).where(PointAccount.owner == owner, PointAccount.program_id == program.id)
    )
    if existing is not None:
        return existing
    row = PointAccount(
        owner=owner,
        program_id=program.id,
        account_ref=_mask_account_ref(account_ref),
        status=status,
        last_activity=last_activity,
        notes=notes,
    )
    session.add(row)
    session.flush()
    return row


def list_accounts(session: Session) -> list[PointAccount]:
    return list(session.scalars(select(PointAccount).order_by(PointAccount.owner, PointAccount.id)))


def create_ledger_transaction(
    session: Session,
    *,
    account_id: int,
    kind: str,
    quantity: Decimal,
    occurred_at: date,
    counterparty_account_id: int | None = None,
    cost_total: Decimal | None = None,
    cost_currency: str | None = None,
    note: str | None = None,
    create_lot: bool = False,
) -> LedgerTransaction:
    kind = kind.strip().lower()
    if kind not in VALID_TRANSACTION_KINDS:
        raise PointWalletError("Unsupported ledger transaction kind")
    account = _require_account(session, account_id)
    if counterparty_account_id is not None:
        _require_account(session, counterparty_account_id)
    row = LedgerTransaction(
        account_id=account.id,
        kind=kind,
        quantity=quantity,
        occurred_at=occurred_at,
        counterparty_account_id=counterparty_account_id,
        cost_total=cost_total,
        cost_currency=cost_currency.upper() if cost_currency else None,
        note=note,
    )
    session.add(row)
    session.flush()
    if create_lot:
        if quantity <= 0 or cost_total is None:
            raise PointWalletError("Manual lot adjustments require positive quantity and cost_total")
        twd_cost = _to_twd(session, cost_total, cost_currency or "TWD", occurred_at)
        session.add(
            CostLot(
                account_id=account.id,
                source_transaction_id=row.id,
                quantity=quantity,
                remaining_quantity=quantity,
                total_cost_twd=twd_cost,
                cost_per_point_twd=_cost_per_point(twd_cost, quantity),
                acquired_at=occurred_at,
            )
        )
    _commit(session)
    return row


def list_ledger_transactions(session: Session, account_id: int | None = None) -> list[LedgerTransaction]:
    statement = select(LedgerTransaction).order_by(LedgerTransaction.occurred_at, LedgerTransaction.id)
    if account_id is not None:
        statement = statement.where(LedgerTransaction.account_id == account_id)
    return list(session.scalars(statement))


def list_cost_lots(session: Session, account_id: int | None = None) -> list[CostLot]:
    statement = select(CostLot).order_by(CostLot.acquired_at, CostLot.id)
    if account_id is not None:
        statement = statement.where(CostLot.account_id == account_id)
    return list(session.scalars(statement))


def create_transfer_rule(
    session: Session,
    *,
    from_program_id: int,
    to_program_id: int,
    ratio_from: Decimal,
    ratio_to: Decimal,
    bonus_pct: Decimal = Decimal("0"),
    min_transfer: Decimal | None = None,
    transfer_days_note: str | None = None,
    valid_from: date,
    valid_until: date | None = None,
) -> TransferRule:
    _require_program(session, from_program_id)
    _require_program(session, to_program_id)
    row = TransferRule(
        from_program_id=from_program_id,
        to_program_id=to_program_id,
        ratio_from=ratio_from,
        ratio_to=ratio_to,
        bonus_pct=bonus_pct,
        min_transfer=min_transfer,
        transfer_days_note=transfer_days_note,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.add(row)
    _commit(session)
    return row


def list_transfer_rules(session: Session) -> list[TransferRule]:
    return list(session.scalars(select(TransferRule).order_by(TransferRule.from_program_id, TransferRule.to_program_id, TransferRule.id)))


def create_purchase_offer(
    session: Session,
    *,
    program_id: int,
    kind: str,
    base_price: Decimal,
    currency: str,
    bonus_pct: Decimal = Decimal("0"),
    min_points: Decimal | None = None,
    max_points: Decimal | None = None,
    start_date: date,
    end_date: date | None = None,
    source_note: str | None = None,
) -> PurchaseOffer:
    _require_program(session, program_id)
    effective_cpp = _effective_cpp(base_price, bonus_pct)
    row = PurchaseOffer(
        program_id=program_id,
        kind=_required(kind, "kind"),
        base_price=base_price,
        currency=currency.upper(),
        bonus_pct=bonus_pct,
        min_points=min_points,
        max_points=max_points,
        effective_cpp=effective_cpp,
        start_date=start_date,
        end_date=end_date,
        source_note=source_note,
    )
    session.add(row)
    _commit(session)
    return row


def list_purchase_offers(session: Session) -> list[PurchaseOffer]:
    return list(session.scalars(select(PurchaseOffer).order_by(PurchaseOffer.program_id, PurchaseOffer.start_date.desc(), PurchaseOffer.id)))


def get_portfolio_summary(session: Session, *, owner: str | None = None, today: date | None = None) -> dict[str, object]:
    today = today or date.today()
    accounts = list_accounts(session)
    if owner is not None:
        normalized_owner = _normalize_owner(owner)
        accounts = [account for account in accounts if account.owner == normalized_owner]
    rows = [_account_summary(session, account) for account in accounts]
    expiry_cutoff = today + timedelta(days=90)
    expiring = [
        row
        for row in rows
        if row.expires_at is not None and today <= row.expires_at <= expiry_cutoff and row.balance > 0
    ]
    return {
        "owners": sorted({row.owner for row in rows}),
        "accounts": rows,
        "expiring_soon": expiring,
        "total_real_cost_basis_twd": sum((row.real_cost_basis_twd for row in rows), Decimal("0")),
    }


def _account_summary(session: Session, account: PointAccount) -> AccountSummary:
    transactions = list_ledger_transactions(session, account.id)
    lots = list_cost_lots(session, account.id)
    balance = sum((transaction.quantity for transaction in transactions), Decimal("0"))
    remaining_quantity = sum((lot.remaining_quantity for lot in lots), Decimal("0"))
    real_cost = sum((lot.total_cost_twd for lot in lots), Decimal("0"))
    avg_cost = _cost_per_point(real_cost, remaining_quantity) if remaining_quantity > 0 else None
    latest_offer = session.scalar(
        select(PurchaseOffer)
        .where(PurchaseOffer.program_id == account.program_id)
        .order_by(PurchaseOffer.start_date.desc(), PurchaseOffer.id.desc())
    )
    market_value = None
    if latest_offer is not None and balance > 0:
        market_value = _to_twd(session, latest_offer.effective_cpp * balance, latest_offer.currency, latest_offer.start_date)
    expiry_dates = [lot.acquired_at for lot in lots if "expires_at=" in (lot.source_transaction.note or "")]
    expires_at = _extract_expiry(transactions)
    return AccountSummary(
        account_id=account.id,
        owner=account.owner,
        program_id=account.program_id,
        program_name=account.program.name,
        program_kind=account.program.kind,
        balance=balance,
        remaining_lot_quantity=remaining_quantity,
        real_cost_basis_twd=real_cost,
        avg_cost_per_point_twd=avg_cost,
        market_value_twd=market_value,
        expires_at=expires_at or (min(expiry_dates) if expiry_dates else None),
    )


def _extract_expiry(transactions: list[LedgerTransaction]) -> date | None:
    expiries: list[date] = []
    for transaction in transactions:
        note = transaction.note or ""
        marker = "expires_at="
        if marker not in note:
            continue
        raw = note.split(marker, 1)[1].split(" ", 1)[0].strip()
        try:
            expiries.append(date.fromisoformat(raw))
        except ValueError:
            continue
    return min(expiries) if expiries else None


def _require_program(session: Session, program_id: int) -> PointProgram:
    row = session.get(PointProgram, program_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    return row


def _require_account(session: Session, account_id: int) -> PointAccount:
    row = session.get(PointAccount, account_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown account_id: {account_id}")
    return row


def _normalize_owner(owner: str) -> str:
    normalized = owner.strip().lower()
    if normalized == "kai":
        normalized = "kent"
    if normalized not in VALID_OWNERS:
        raise PointWalletError("owner must be kent or wife")
    return normalized


def _required(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise PointWalletError(f"{field} is required")
    return cleaned


def _mask_account_ref(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) <= 4:
        return "***"
    return f"***{cleaned[-4:]}"


def _to_twd(session: Session, amount: Decimal, currency: str, as_of: date) -> Decimal:
    return (amount * get_twd_per_unit(session, currency, as_of=as_of)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _cost_per_point(total_cost: Decimal, quantity: Decimal) -> Decimal:
    return (total_cost / quantity).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _effective_cpp(base_price: Decimal, bonus_pct: Decimal) -> Decimal:
    multiplier = Decimal("1") + (bonus_pct / Decimal("100"))
    return (base_price / multiplier).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
