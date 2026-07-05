"""add trade history tables

Revision ID: 0008_trade_history
Revises: 0007_brain_review_llm_meta
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_trade_history"
down_revision: str | None = "0007_brain_review_llm_meta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("fill_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cash_row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_table(
        "trade_fills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.Column("executed_at_raw", sa.Text(), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("position_effect", sa.Text(), nullable=False),
        sa.Column("instrument_type", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("net_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("order_type", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), server_default="USD", nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cash_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("txn_time", sa.Text(), nullable=True),
        sa.Column("ref_no", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("misc_fees", sa.Numeric(18, 2), nullable=True),
        sa.Column("commissions_fees", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.Text(), server_default="USD", nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "realized_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("avg_entry", sa.Numeric(18, 6), nullable=False),
        sa.Column("avg_exit", sa.Numeric(18, 6), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("holding_period_seconds", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("realized_trades")
    op.drop_table("cash_transactions")
    op.drop_table("trade_fills")
    op.drop_table("import_batches")
