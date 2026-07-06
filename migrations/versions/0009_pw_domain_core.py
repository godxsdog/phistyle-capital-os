"""add point wallet domain core

Revision ID: 0009_pw_domain_core
Revises: 0008_trade_history
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_pw_domain_core"
down_revision: str | None = "0008_trade_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("expiry_rule_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("account_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("last_activity", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner", "program_id"),
    )
    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 2), nullable=False),
        sa.Column("occurred_at", sa.Date(), nullable=False),
        sa.Column("counterparty_account_id", sa.Integer(), nullable=True),
        sa.Column("cost_total", sa.Numeric(18, 2), nullable=True),
        sa.Column("cost_currency", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["counterparty_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cost_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("source_transaction_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 2), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_cost_twd", sa.Numeric(18, 2), nullable=False),
        sa.Column("cost_per_point_twd", sa.Numeric(12, 6), nullable=False),
        sa.Column("acquired_at", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_transaction_id"], ["ledger_transactions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "transfer_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_program_id", sa.Integer(), nullable=False),
        sa.Column("to_program_id", sa.Integer(), nullable=False),
        sa.Column("ratio_from", sa.Numeric(18, 2), nullable=False),
        sa.Column("ratio_to", sa.Numeric(18, 2), nullable=False),
        sa.Column("bonus_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("min_transfer", sa.Numeric(18, 2), nullable=True),
        sa.Column("transfer_days_note", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["from_program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "purchase_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("base_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("bonus_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("min_points", sa.Numeric(18, 2), nullable=True),
        sa.Column("max_points", sa.Numeric(18, 2), nullable=True),
        sa.Column("effective_cpp", sa.Numeric(18, 6), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("twd_per_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("currency", "as_of"),
    )


def downgrade() -> None:
    op.drop_table("fx_rates")
    op.drop_table("purchase_offers")
    op.drop_table("transfer_rules")
    op.drop_table("cost_lots")
    op.drop_table("ledger_transactions")
    op.drop_table("accounts")
    op.drop_table("programs")
