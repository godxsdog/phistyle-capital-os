"""add hotel vouchers and voucher expiry alerts

Revision ID: 0016_pw4_vouchers
Revises: 0015_backtest_engine
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0016_pw4_vouchers"
down_revision: str | None = "0015_backtest_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hotel_vouchers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("face_value_points", sa.Numeric(18, 0), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("acquired_note", sa.Text(), nullable=True),
        sa.Column("used_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("expiry_alerts", sa.Column("voucher_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_expiry_alerts_voucher_id_hotel_vouchers",
        "expiry_alerts",
        "hotel_vouchers",
        ["voucher_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_expiry_alerts_voucher_threshold",
        "expiry_alerts",
        ["voucher_id", "threshold_days", "expires_at", "checked_on"],
    )
    # Phase PW-4 D1 explicitly allows this low-risk ALTER exception so one
    # expiry_alert row can refer to either an account or a hotel voucher.
    op.alter_column("expiry_alerts", "account_id", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        "ck_expiry_alerts_one_subject",
        "expiry_alerts",
        "(account_id IS NULL) != (voucher_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_expiry_alerts_one_subject", "expiry_alerts", type_="check")
    op.alter_column("expiry_alerts", "account_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("uq_expiry_alerts_voucher_threshold", "expiry_alerts", type_="unique")
    op.drop_constraint("fk_expiry_alerts_voucher_id_hotel_vouchers", "expiry_alerts", type_="foreignkey")
    op.drop_column("expiry_alerts", "voucher_id")
    op.drop_table("hotel_vouchers")
