from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import Base


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_request_id: Mapped[int] = mapped_column(
        ForeignKey("decision_requests.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    market: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    planned_entry: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    stop_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    declared_capital_twd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_spec_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_paper: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    risk_check: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanMark(Base):
    __tablename__ = "plan_marks"
    __table_args__ = (UniqueConstraint("trade_plan_id", "mark_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_plan_id: Mapped[int] = mapped_column(ForeignKey("trade_plans.id", ondelete="CASCADE"), nullable=False)
    mark_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class PlanOutcome(Base):
    __tablename__ = "plan_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_plan_id: Mapped[int] = mapped_column(
        ForeignKey("trade_plans.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    exit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    exit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    stop_respected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    holding_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_vs_actual: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
