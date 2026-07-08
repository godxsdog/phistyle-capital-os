from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.base import Base


class ToolMonitorSetting(Base):
    __tablename__ = "tool_monitor_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flight_no: Mapped[str] = mapped_column(Text, nullable=False, default="AK1511")
    flight_date: Mapped[date] = mapped_column(Date, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
