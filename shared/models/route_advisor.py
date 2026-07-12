from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import Base
from shared.models.knowledge import KnowledgeDocument
from shared.models.point_wallet import PointProgram


class RouteSweetSpot(Base):
    __tablename__ = "route_sweet_spots"
    __table_args__ = (
        CheckConstraint(
            "status IN ('未確認', '已確認', '已否決')",
            name="ck_route_sweet_spots_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    origin_tag: Mapped[str] = mapped_column(Text, nullable=False, default="TPE")
    dest_tag: Mapped[str] = mapped_column(Text, nullable=False)
    cabin: Mapped[str] = mapped_column(Text, nullable=False)
    miles_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 0), nullable=True)
    tip: Mapped[str] = mapped_column(Text, nullable=False)
    caveats: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_doc_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="未確認")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(UTC)
    )

    program: Mapped[PointProgram] = relationship()
    source_document: Mapped[KnowledgeDocument] = relationship()


class DestRegion(Base):
    __tablename__ = "dest_regions"

    airport: Mapped[str] = mapped_column(Text, primary_key=True)
    region: Mapped[str] = mapped_column(Text, nullable=False)
