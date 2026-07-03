"""add human reviews

Revision ID: 0006_add_human_reviews
Revises: 0005_add_brain_reviews
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_add_human_reviews"
down_revision: str | None = "0005_add_brain_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


human_review_decision = postgresql.ENUM(
    "approve",
    "reject",
    name="human_review_decision",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    human_review_decision.create(bind, checkfirst=True)

    op.create_table(
        "human_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_log_id", sa.Integer(), nullable=False),
        sa.Column("decision_request_id", sa.Integer(), nullable=False),
        sa.Column("brain_review_id", sa.Integer(), nullable=True),
        sa.Column("reviewer", sa.String(length=120), nullable=False),
        sa.Column("review_decision", human_review_decision, nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brain_review_id"],
            ["brain_reviews.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decision_log_id"],
            ["decision_log.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decision_request_id"],
            ["decision_requests.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_log_id", name="uq_human_reviews_decision_log_id"),
    )
    op.create_index(op.f("ix_human_reviews_decision_log_id"), "human_reviews", ["decision_log_id"], unique=False)
    op.create_index(
        op.f("ix_human_reviews_decision_request_id"),
        "human_reviews",
        ["decision_request_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(op.f("ix_human_reviews_decision_request_id"), table_name="human_reviews")
    op.drop_index(op.f("ix_human_reviews_decision_log_id"), table_name="human_reviews")
    op.drop_table("human_reviews")

    human_review_decision.drop(bind, checkfirst=True)
