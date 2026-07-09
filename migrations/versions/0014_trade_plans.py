"""add trade plan pipeline tables

Revision ID: 0014_trade_plans
Revises: 0013_tool_monitor
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0014_trade_plans"
down_revision: str | None = "0013_tool_monitor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trade_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_request_id", sa.Integer(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("planned_entry", sa.Numeric(18, 6), nullable=False),
        sa.Column("stop_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("target_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("declared_capital_twd", sa.Numeric(18, 2), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("strategy_spec_id", sa.Integer(), nullable=True),
        sa.Column("is_paper", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("risk_check", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["decision_request_id"], ["decision_requests.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_request_id"),
    )
    op.create_table(
        "plan_marks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_plan_id", sa.Integer(), nullable=False),
        sa.Column("mark_date", sa.Date(), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 6), nullable=False),
        sa.ForeignKeyConstraint(["trade_plan_id"], ["trade_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_plan_id", "mark_date"),
    )
    op.create_table(
        "plan_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_plan_id", sa.Integer(), nullable=False),
        sa.Column("exit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(18, 2), nullable=False),
        sa.Column("stop_respected", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("holding_days", sa.Integer(), nullable=True),
        sa.Column("planned_vs_actual", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["trade_plan_id"], ["trade_plans.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_plan_id"),
    )


def downgrade() -> None:
    op.drop_table("plan_outcomes")
    op.drop_table("plan_marks")
    op.drop_table("trade_plans")
