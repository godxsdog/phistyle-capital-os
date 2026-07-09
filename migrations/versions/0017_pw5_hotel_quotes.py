"""add hotel stay quotes

Revision ID: 0017_pw5_hotel_quotes
Revises: 0016_pw4_vouchers
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0017_pw5_hotel_quotes"
down_revision: str | None = "0016_pw4_vouchers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hotel_stay_quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("hotel_name", sa.Text(), nullable=False),
        sa.Column("stay_date", sa.Date(), nullable=False),
        sa.Column("nights", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("cash_price_twd", sa.Numeric(18, 2), nullable=False),
        sa.Column("points_price_per_night", sa.Numeric(18, 0), nullable=False),
        sa.Column("taxes_note", sa.Text(), nullable=True),
        sa.Column("topup_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("topup_points", sa.Numeric(18, 0), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("hotel_stay_quotes")
