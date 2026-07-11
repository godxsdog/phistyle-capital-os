"""add multi-segment trip quest fields

Revision ID: 0019_pw7_multi_segment
Revises: 0018_pw6_trip_quests
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0019_pw7_multi_segment"
down_revision: str | None = "0018_pw6_trip_quests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trip_quests",
        sa.Column("kind", sa.Text(), nullable=False, server_default="round_trip"),
    )
    op.add_column("trip_quests", sa.Column("segments_json", sa.Text(), nullable=True))
    op.add_column("quest_results", sa.Column("segments_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("quest_results", "segments_json")
    op.drop_column("trip_quests", "segments_json")
    op.drop_column("trip_quests", "kind")
