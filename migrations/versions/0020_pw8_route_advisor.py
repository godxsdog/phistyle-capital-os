"""add route advisor knowledge tables

Revision ID: 0020_pw8_route_advisor
Revises: 0019_pw7_multi_segment
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020_pw8_route_advisor"
down_revision: str | None = "0019_pw7_multi_segment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEST_REGION_ROWS = [
    {"airport": airport, "region": region}
    for region, airports in {
        "日本": "NRT HND KIX ITM NGO FUK CTS OKA",
        "韓國": "ICN GMP PUS",
        "港澳中": "HKG MFM PVG PEK CAN",
        "東南亞": "SIN BKK KUL CGK MNL SGN HAN DAD",
        "南亞/島嶼": "MLE DEL BOM CMB",
        "歐洲": "LHR CDG FRA AMS ZRH IST MXP FCO MAD VIE MUC",
        "北美": "LAX SFO SEA JFK ORD BOS YVR HNL",
        "澳紐": "SYD MEL BNE AKL",
        "中東": "DXB DOH AUH",
    }.items()
    for airport in airports.split()
]


def upgrade() -> None:
    op.create_table(
        "dest_regions",
        sa.Column("airport", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("airport"),
    )
    dest_regions = sa.table(
        "dest_regions",
        sa.column("airport", sa.Text()),
        sa.column("region", sa.Text()),
    )
    op.bulk_insert(dest_regions, DEST_REGION_ROWS)
    op.create_table(
        "route_sweet_spots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("origin_tag", sa.Text(), nullable=False, server_default="TPE"),
        sa.Column("dest_tag", sa.Text(), nullable=False),
        sa.Column("cabin", sa.Text(), nullable=False),
        sa.Column("miles_cost", sa.Numeric(18, 0), nullable=True),
        sa.Column("tip", sa.Text(), nullable=False),
        sa.Column("caveats", sa.Text(), nullable=True),
        sa.Column("source_doc_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="未確認"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('未確認', '已確認', '已否決')",
            name="ck_route_sweet_spots_status",
        ),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_doc_id"], ["knowledge_documents.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("route_sweet_spots")
    op.drop_table("dest_regions")
