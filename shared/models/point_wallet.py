from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import Base


class PointProgram(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    expiry_rule_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PointAccount(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("owner", "program_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False)
    account_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    last_activity: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped[PointProgram] = relationship()


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    occurred_at: Mapped[date] = mapped_column(Date, nullable=False)
    counterparty_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True)
    cost_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[PointAccount] = relationship(foreign_keys=[account_id])
    counterparty_account: Mapped[PointAccount | None] = relationship(foreign_keys=[counterparty_account_id])


class CostLot(Base):
    __tablename__ = "cost_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    source_transaction_id: Mapped[int] = mapped_column(ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_cost_twd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost_per_point_twd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    acquired_at: Mapped[date] = mapped_column(Date, nullable=False)

    account: Mapped[PointAccount] = relationship()
    source_transaction: Mapped[LedgerTransaction] = relationship()


class TransferRule(Base):
    __tablename__ = "transfer_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False)
    to_program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False)
    ratio_from: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    ratio_to: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    bonus_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    min_transfer: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    transfer_days_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    rule_kind: Mapped[str] = mapped_column(Text, nullable=False, default="linear")
    block_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    block_bonus_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    from_program: Mapped[PointProgram] = relationship(foreign_keys=[from_program_id])
    to_program: Mapped[PointProgram] = relationship(foreign_keys=[to_program_id])


class PurchaseOffer(Base):
    __tablename__ = "purchase_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    bonus_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    min_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    max_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    effective_cpp: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    fees: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    rebate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    points_received: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped[PointProgram] = relationship()


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("currency", "as_of"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    twd_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)


class AwardQuote(Base):
    __tablename__ = "award_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    travel_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cabin: Mapped[str | None] = mapped_column(Text, nullable=True)
    pax: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False)
    miles_required: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    taxes_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    taxes_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    cash_price_twd: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(UTC))

    program: Mapped[PointProgram] = relationship()


class FundingScenario(Base):
    __tablename__ = "funding_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_quote_id: Mapped[int] = mapped_column(ForeignKey("award_quotes.id", ondelete="CASCADE"), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(nullable=False)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    path_json: Mapped[str] = mapped_column(Text, nullable=False)
    true_cost_twd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    saving_vs_cash_twd: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_cpp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    total_cash_cost_twd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    points_acquired: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    points_consumed: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    points_leftover: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    award_quote: Mapped[AwardQuote] = relationship()


class AwardWatch(Base):
    __tablename__ = "award_watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    cabin: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(UTC))

    program: Mapped[PointProgram | None] = relationship()


class AwardSnapshot(Base):
    __tablename__ = "award_snapshots"
    __table_args__ = (UniqueConstraint("watch_id", "seen_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int] = mapped_column(ForeignKey("award_watches.id", ondelete="CASCADE"), nullable=False)
    seen_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalized_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(UTC))

    watch: Mapped[AwardWatch] = relationship()


class ExpiryAlert(Base):
    __tablename__ = "expiry_alerts"
    __table_args__ = (UniqueConstraint("account_id", "threshold_days", "expires_at", "checked_on"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    threshold_days: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[date] = mapped_column(Date, nullable=False)
    checked_on: Mapped[date] = mapped_column(Date, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(UTC))

    account: Mapped[PointAccount] = relationship()
