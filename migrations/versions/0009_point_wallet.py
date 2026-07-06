"""add point wallet tables

Revision ID: 0009_point_wallet
Revises: 0008_trade_history
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_point_wallet"
down_revision: str | None = "0008_trade_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loyalty_programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "point_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["loyalty_programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "valuation_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("twd_per_point", sa.Numeric(12, 6), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["loyalty_programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "effective_date"),
    )
    op.create_table(
        "transfer_partners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_program_id", sa.Integer(), nullable=False),
        sa.Column("to_program_id", sa.Integer(), nullable=False),
        sa.Column("ratio_from", sa.Integer(), nullable=False),
        sa.Column("ratio_to", sa.Integer(), nullable=False),
        sa.Column("transfer_days", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["from_program_id"], ["loyalty_programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_program_id"], ["loyalty_programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_program_id", "to_program_id"),
    )
    op.create_table(
        "award_watches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("cabin", sa.Text(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["loyalty_programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "award_availability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watch_id", sa.Integer(), nullable=False),
        sa.Column("seen_date", sa.Date(), nullable=False),
        sa.Column("flight_date", sa.Date(), nullable=False),
        sa.Column("program", sa.Text(), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=True),
        sa.Column("miles_cost", sa.Numeric(18, 0), nullable=True),
        sa.Column("taxes_fees", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("raw", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["watch_id"], ["award_watches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watch_id", "seen_date", "flight_date", "program", "source"),
    )


def downgrade() -> None:
    op.drop_table("award_availability")
    op.drop_table("award_watches")
    op.drop_table("transfer_partners")
    op.drop_table("valuation_rates")
    op.drop_table("point_balances")
    op.drop_table("loyalty_programs")
