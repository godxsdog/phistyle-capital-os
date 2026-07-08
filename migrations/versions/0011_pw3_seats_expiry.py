"""add point wallet seats aero and expiry alerts

Revision ID: 0011_pw3_seats_expiry
Revises: 0010_pw_award_cost
Create Date: 2026-07-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011_pw3_seats_expiry"
down_revision: str | None = "0010_pw_award_cost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "award_watches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("cabin", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("program_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "award_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watch_id", sa.Integer(), nullable=False),
        sa.Column("seen_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("normalized_json", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["watch_id"], ["award_watches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watch_id", "seen_date"),
    )
    op.create_table(
        "expiry_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("threshold_days", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "threshold_days", "expires_at", "checked_on"),
    )


def downgrade() -> None:
    op.drop_table("expiry_alerts")
    op.drop_table("award_snapshots")
    op.drop_table("award_watches")
