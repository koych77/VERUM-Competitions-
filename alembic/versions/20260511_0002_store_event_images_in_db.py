"""store event images in db

Revision ID: 20260511_0002
Revises: 20260511_0001
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_0002"
down_revision = "20260511_0001"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("events", "image_content"):
        op.add_column("events", sa.Column("image_content", sa.LargeBinary(), nullable=True))
    if not _has_column("events", "image_content_type"):
        op.add_column("events", sa.Column("image_content_type", sa.String(length=80), nullable=True))


def downgrade() -> None:
    if _has_column("events", "image_content_type"):
        op.drop_column("events", "image_content_type")
    if _has_column("events", "image_content"):
        op.drop_column("events", "image_content")
