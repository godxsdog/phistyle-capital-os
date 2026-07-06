from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import Base


class LoyaltyProgram(Base):
    __tablename__ = "loyalty_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PointBalance(Base):
    __tablename__ = "point_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("loyalty_programs.id", ondelete="RESTRICT"), nullable=False)
    balance: Mapped[Numeric] = mapped_column(Numeric(18, 2), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    program: Mapped[LoyaltyProgram] = relationship()


class ValuationRate(Base):
    __tablename__ = "valuation_rates"
    __table_args__ = (UniqueConstraint("program_id", "effective_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("loyalty_programs.id", ondelete="RESTRICT"), nullable=False)
    twd_per_point: Mapped[Numeric] = mapped_column(Numeric(12, 6), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped[LoyaltyProgram] = relationship()


class TransferPartner(Base):
    __tablename__ = "transfer_partners"
    __table_args__ = (UniqueConstraint("from_program_id", "to_program_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_program_id: Mapped[int] = mapped_column(ForeignKey("loyalty_programs.id", ondelete="RESTRICT"), nullable=False)
    to_program_id: Mapped[int] = mapped_column(ForeignKey("loyalty_programs.id", ondelete="RESTRICT"), nullable=False)
    ratio_from: Mapped[int] = mapped_column(Integer, nullable=False)
    ratio_to: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_days: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    from_program: Mapped[LoyaltyProgram] = relationship(foreign_keys=[from_program_id])
    to_program: Mapped[LoyaltyProgram] = relationship(foreign_keys=[to_program_id])


class AwardWatch(Base):
    __tablename__ = "award_watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    cabin: Mapped[str] = mapped_column(Text, nullable=False)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("loyalty_programs.id", ondelete="RESTRICT"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)

    program: Mapped[LoyaltyProgram | None] = relationship()


class AwardAvailability(Base):
    __tablename__ = "award_availability"
    __table_args__ = (UniqueConstraint("watch_id", "seen_date", "flight_date", "program", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int] = mapped_column(ForeignKey("award_watches.id", ondelete="CASCADE"), nullable=False)
    seen_date: Mapped[date] = mapped_column(Date, nullable=False)
    flight_date: Mapped[date] = mapped_column(Date, nullable=False)
    program: Mapped[str] = mapped_column(Text, nullable=False)
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    miles_cost: Mapped[Numeric | None] = mapped_column(Numeric(18, 0), nullable=True)
    taxes_fees: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    watch: Mapped[AwardWatch] = relationship()
