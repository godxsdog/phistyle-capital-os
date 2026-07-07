"""add point wallet award cost engine

Revision ID: 0010_pw_award_cost
Revises: 0009_pw_domain_core
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0010_pw_award_cost"
down_revision: str | None = "0009_pw_domain_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transfer_rules", sa.Column("rule_kind", sa.Text(), nullable=False, server_default="linear"))
    op.add_column("transfer_rules", sa.Column("block_size", sa.Numeric(18, 2), nullable=True))
    op.add_column("transfer_rules", sa.Column("block_bonus_points", sa.Numeric(18, 2), nullable=True))
    op.add_column("transfer_rules", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("purchase_offers", sa.Column("paid_amount", sa.Numeric(18, 2), nullable=True))
    op.add_column("purchase_offers", sa.Column("fees", sa.Numeric(18, 2), nullable=True))
    op.add_column("purchase_offers", sa.Column("rebate", sa.Numeric(18, 2), nullable=True))
    op.add_column("purchase_offers", sa.Column("points_received", sa.Numeric(18, 2), nullable=True))
    op.add_column("purchase_offers", sa.Column("source_url", sa.Text(), nullable=True))
    op.create_table(
        "award_quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("destination", sa.Text(), nullable=True),
        sa.Column("travel_date", sa.Date(), nullable=True),
        sa.Column("cabin", sa.Text(), nullable=True),
        sa.Column("pax", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("miles_required", sa.Numeric(18, 0), nullable=False),
        sa.Column("taxes_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("taxes_currency", sa.Text(), nullable=True),
        sa.Column("cash_price_twd", sa.Numeric(18, 2), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "funding_scenarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("award_quote_id", sa.Integer(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("path_json", sa.Text(), nullable=False),
        sa.Column("true_cost_twd", sa.Numeric(18, 2), nullable=False),
        sa.Column("saving_vs_cash_twd", sa.Numeric(18, 2), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.Column("effective_cpp", sa.Numeric(18, 6), nullable=True),
        sa.Column("total_cash_cost_twd", sa.Numeric(18, 2), nullable=False),
        sa.Column("points_acquired", sa.Numeric(18, 2), nullable=False),
        sa.Column("points_consumed", sa.Numeric(18, 2), nullable=False),
        sa.Column("points_leftover", sa.Numeric(18, 2), nullable=False),
        sa.ForeignKeyConstraint(["award_quote_id"], ["award_quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("funding_scenarios")
    op.drop_table("award_quotes")
    op.drop_column("purchase_offers", "points_received")
    op.drop_column("purchase_offers", "source_url")
    op.drop_column("purchase_offers", "rebate")
    op.drop_column("purchase_offers", "fees")
    op.drop_column("purchase_offers", "paid_amount")
    op.drop_column("transfer_rules", "source_url")
    op.drop_column("transfer_rules", "block_bonus_points")
    op.drop_column("transfer_rules", "block_size")
    op.drop_column("transfer_rules", "rule_kind")
