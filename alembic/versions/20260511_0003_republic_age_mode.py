"""add republic age mode

Revision ID: 20260511_0003
Revises: 20260511_0002
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_0003"
down_revision = "20260511_0002"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("events", "is_republic_championship"):
        op.add_column(
            "events",
            sa.Column("is_republic_championship", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    if _has_column("events", "is_republic_championship"):
        op.drop_column("events", "is_republic_championship")
