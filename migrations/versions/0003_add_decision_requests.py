"""add decision requests

Revision ID: 0003_add_decision_requests
Revises: 0002_add_knowledge_memory_tables
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_add_decision_requests"
down_revision: str | None = "0002_add_knowledge_memory_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


decision_request_type = postgresql.ENUM(
    "investment",
    "travel",
    "credit_card",
    "medical",
    "engineering",
    "personal",
    "architecture",
    name="decision_request_type",
    create_type=False,
)
decision_request_risk_level = postgresql.ENUM(
    "low",
    "medium",
    "high",
    name="decision_request_risk_level",
    create_type=False,
)
decision_request_status = postgresql.ENUM(
    "draft",
    "submitted",
    "triaged",
    "brain_reviewed",
    "human_approved",
    "rejected",
    "archived",
    name="decision_request_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    decision_request_type.create(bind, checkfirst=True)
    decision_request_risk_level.create(bind, checkfirst=True)
    decision_request_status.create(bind, checkfirst=True)

    op.create_table(
        "decision_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_id", sa.String(length=120), nullable=False),
        sa.Column("decision_type", decision_request_type, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("risk_level", decision_request_risk_level, nullable=False),
        sa.Column("status", decision_request_status, nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("related_knowledge_document_id", sa.Integer(), nullable=True),
        sa.Column("related_decision_log_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["related_decision_log_id"],
            ["decision_log.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["related_knowledge_document_id"],
            ["knowledge_documents.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_requests_app_id"), "decision_requests", ["app_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index(op.f("ix_decision_requests_app_id"), table_name="decision_requests")
    op.drop_table("decision_requests")

    decision_request_status.drop(bind, checkfirst=True)
    decision_request_risk_level.drop(bind, checkfirst=True)
    decision_request_type.drop(bind, checkfirst=True)

