"""add idempotent broadcast delivery log

Revision ID: 20260825_0008
Revises: 20260825_0007
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_0008"
down_revision = "20260825_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broadcast_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_key", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parts_sent", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_key", "user_id", name="uq_broadcast_campaign_user"),
    )
    op.create_index("ix_broadcast_deliveries_campaign_key", "broadcast_deliveries", ["campaign_key"])
    op.create_index("ix_broadcast_deliveries_status", "broadcast_deliveries", ["status"])
    op.create_index("ix_broadcast_deliveries_user_id", "broadcast_deliveries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_broadcast_deliveries_user_id", table_name="broadcast_deliveries")
    op.drop_index("ix_broadcast_deliveries_status", table_name="broadcast_deliveries")
    op.drop_index("ix_broadcast_deliveries_campaign_key", table_name="broadcast_deliveries")
    op.drop_table("broadcast_deliveries")
