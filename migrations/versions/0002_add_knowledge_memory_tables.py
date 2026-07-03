"""add knowledge memory tables

Revision ID: 0002_add_knowledge_memory_tables
Revises:
Create Date: 2026-07-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_knowledge_memory_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


knowledge_source_type = sa.Enum(
    "manual",
    "agent_generated",
    "import",
    name="knowledge_source_type",
)
storage_backend = sa.Enum(
    "local",
    "nas",
    "external",
    name="storage_backend",
)
agent_memory_type = sa.Enum(
    "observation",
    "summary",
    "decision_context",
    name="agent_memory_type",
)
memory_importance = sa.Enum(
    "low",
    "medium",
    "high",
    name="memory_importance",
)
decision_status = sa.Enum(
    "proposed",
    "approved",
    "rejected",
    name="decision_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    knowledge_source_type.create(bind, checkfirst=True)
    storage_backend.create(bind, checkfirst=True)
    agent_memory_type.create(bind, checkfirst=True)
    memory_importance.create(bind, checkfirst=True)
    decision_status.create(bind, checkfirst=True)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", knowledge_source_type, nullable=False),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("storage_backend", storage_backend, nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=120), nullable=False),
        sa.Column("memory_type", agent_memory_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("importance", memory_importance, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_memory_agent_id"), "agent_memory", ["agent_id"], unique=False)
    op.create_table(
        "decision_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("proposed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("approved_by", sa.String(length=120), nullable=True),
        sa.Column("status", decision_status, nullable=False),
        sa.Column("related_request_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("decision_log")
    op.drop_index(op.f("ix_agent_memory_agent_id"), table_name="agent_memory")
    op.drop_table("agent_memory")
    op.drop_table("knowledge_documents")

    decision_status.drop(bind, checkfirst=True)
    memory_importance.drop(bind, checkfirst=True)
    agent_memory_type.drop(bind, checkfirst=True)
    storage_backend.drop(bind, checkfirst=True)
    knowledge_source_type.drop(bind, checkfirst=True)

