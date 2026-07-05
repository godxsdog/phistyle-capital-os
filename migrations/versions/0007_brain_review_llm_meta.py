"""add brain review llm metadata

Revision ID: 0007_brain_review_llm_meta
Revises: 0006_add_human_reviews
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_brain_review_llm_meta"
down_revision: str | None = "0006_add_human_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("brain_reviews", sa.Column("llm_backed", sa.Boolean(), nullable=True))
    op.add_column("brain_reviews", sa.Column("llm_provider", sa.Text(), nullable=True))
    op.add_column("brain_reviews", sa.Column("llm_model", sa.Text(), nullable=True))
    op.add_column("brain_reviews", sa.Column("llm_fallback_reason", sa.Text(), nullable=True))
    op.add_column("brain_reviews", sa.Column("llm_floor_applied", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("brain_reviews", "llm_floor_applied")
    op.drop_column("brain_reviews", "llm_fallback_reason")
    op.drop_column("brain_reviews", "llm_model")
    op.drop_column("brain_reviews", "llm_provider")
    op.drop_column("brain_reviews", "llm_backed")
