"""record team registration fields managed by legacy startup DDL

Revision ID: 20260825_0007
Revises: 20260519_0006
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_0007"
down_revision = "20260519_0006"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("registrations", "team_name"):
        op.add_column("registrations", sa.Column("team_name", sa.String(length=255), nullable=True))
    if not _has_column("registrations", "team_members"):
        op.add_column("registrations", sa.Column("team_members", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("registrations", "team_members"):
        op.drop_column("registrations", "team_members")
    if _has_column("registrations", "team_name"):
        op.drop_column("registrations", "team_name")
