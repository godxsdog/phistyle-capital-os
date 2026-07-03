"""add triage results

Revision ID: 0004_add_triage_results
Revises: 0003_add_decision_requests
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_add_triage_results"
down_revision: str | None = "0003_add_decision_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


triage_risk_level = postgresql.ENUM(
    "low",
    "medium",
    "high",
    name="triage_risk_level",
    create_type=False,
)
triage_recommendation = postgresql.ENUM(
    "handle_locally",
    "use_worker_model",
    "escalate_to_brain",
    "reject_request",
    name="triage_recommendation",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    triage_risk_level.create(bind, checkfirst=True)
    triage_recommendation.create(bind, checkfirst=True)

    op.create_table(
        "triage_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_request_id", sa.Integer(), nullable=False),
        sa.Column("risk_level", triage_risk_level, nullable=False),
        sa.Column("recommendation", triage_recommendation, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("flags", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_request_id"],
            ["decision_requests.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_triage_results_decision_request_id"),
        "triage_results",
        ["decision_request_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(op.f("ix_triage_results_decision_request_id"), table_name="triage_results")
    op.drop_table("triage_results")

    triage_recommendation.drop(bind, checkfirst=True)
    triage_risk_level.drop(bind, checkfirst=True)

