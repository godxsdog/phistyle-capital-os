"""add brain reviews

Revision ID: 0005_add_brain_reviews
Revises: 0004_add_triage_results
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_add_brain_reviews"
down_revision: str | None = "0004_add_triage_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


brain_review_recommendation = postgresql.ENUM(
    "proceed",
    "request_more_context",
    "reject",
    "defer",
    "human_review_required",
    name="brain_review_recommendation",
    create_type=False,
)
brain_review_confidence = postgresql.ENUM(
    "low",
    "medium",
    "high",
    name="brain_review_confidence",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    brain_review_recommendation.create(bind, checkfirst=True)
    brain_review_confidence.create(bind, checkfirst=True)

    op.create_table(
        "brain_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_request_id", sa.Integer(), nullable=False),
        sa.Column("triage_result_id", sa.Integer(), nullable=True),
        sa.Column("recommendation", brain_review_recommendation, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", brain_review_confidence, nullable=False),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("required_human_approval", sa.Boolean(), nullable=False),
        sa.Column("proposed_decision_log_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_request_id"],
            ["decision_requests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_decision_log_id"],
            ["decision_log.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["triage_result_id"],
            ["triage_results.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_brain_reviews_decision_request_id"),
        "brain_reviews",
        ["decision_request_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(op.f("ix_brain_reviews_decision_request_id"), table_name="brain_reviews")
    op.drop_table("brain_reviews")

    brain_review_confidence.drop(bind, checkfirst=True)
    brain_review_recommendation.drop(bind, checkfirst=True)

