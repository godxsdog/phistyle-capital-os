"""add trip quests and award quote note

Revision ID: 0018_pw6_trip_quests
Revises: 0017_pw5_hotel_quotes
Create Date: 2026-07-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0018_pw6_trip_quests"
down_revision: str | None = "0017_pw5_hotel_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("award_quotes", sa.Column("note", sa.Text(), nullable=True))
    op.create_table(
        "trip_quests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("programs", sa.Text(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("trip_days", sa.Integer(), nullable=False),
        sa.Column("cabin", sa.Text(), nullable=False),
        sa.Column("pax", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "quest_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_quest_id", sa.Integer(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("program", sa.Text(), nullable=False),
        sa.Column("outbound_date", sa.Date(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("outbound_miles", sa.Numeric(18, 0), nullable=False),
        sa.Column("return_miles", sa.Numeric(18, 0), nullable=False),
        sa.Column("total_miles", sa.Numeric(18, 0), nullable=False),
        sa.Column("outbound_taxes", sa.Text(), nullable=True),
        sa.Column("return_taxes", sa.Text(), nullable=True),
        sa.Column("seats_min", sa.Integer(), nullable=False),
        sa.Column("raw_refs", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["trip_quest_id"], ["trip_quests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_quest_id", "run_date", "rank"),
    )


def downgrade() -> None:
    op.drop_table("quest_results")
    op.drop_table("trip_quests")
    op.drop_column("award_quotes", "note")
