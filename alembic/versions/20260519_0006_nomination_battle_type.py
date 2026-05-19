"""add nomination battle type

Revision ID: 20260519_0006
Revises: 20260519_0005
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260519_0006"
down_revision = "20260519_0005"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("nominations", "battle_type"):
        op.add_column(
            "nominations",
            sa.Column("battle_type", sa.String(length=20), nullable=False, server_default="solo"),
        )


def downgrade() -> None:
    if _has_column("nominations", "battle_type"):
        op.drop_column("nominations", "battle_type")
