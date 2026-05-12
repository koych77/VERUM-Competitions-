"""use bigint for telegram ids

Revision ID: 20260512_0004
Revises: 20260511_0003
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_0004"
down_revision = "20260511_0003"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names() and column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def upgrade() -> None:
    if _has_column("users", "telegram_id"):
        op.alter_column("users", "telegram_id", existing_type=sa.Integer(), type_=sa.BigInteger())


def downgrade() -> None:
    if _has_column("users", "telegram_id"):
        op.alter_column("users", "telegram_id", existing_type=sa.BigInteger(), type_=sa.Integer())
