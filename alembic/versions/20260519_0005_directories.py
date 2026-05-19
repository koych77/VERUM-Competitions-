"""add trainer and club directories

Revision ID: 20260519_0005
Revises: 20260512_0004
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260519_0005"
down_revision = "20260512_0004"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    directory_kind = sa.Enum("trainer", "club", name="directorykind")
    if bind.dialect.name != "sqlite":
        directory_kind.create(bind, checkfirst=True)
    if not _has_table("directory_entries"):
        op.create_table(
            "directory_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.Enum("trainer", "club", name="directorykind", create_type=False), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("normalized_key", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("kind", "normalized_key", name="uq_directory_entry_kind_key"),
        )
        op.create_index(op.f("ix_directory_entries_kind"), "directory_entries", ["kind"], unique=False)
    if not _has_table("directory_aliases"):
        op.create_table(
            "directory_aliases",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.Enum("trainer", "club", name="directorykind", create_type=False), nullable=False),
            sa.Column("alias", sa.String(length=255), nullable=False),
            sa.Column("normalized_key", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["entry_id"], ["directory_entries.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("kind", "normalized_key", name="uq_directory_alias_kind_key"),
        )
        op.create_index(op.f("ix_directory_aliases_entry_id"), "directory_aliases", ["entry_id"], unique=False)
        op.create_index(op.f("ix_directory_aliases_kind"), "directory_aliases", ["kind"], unique=False)


def downgrade() -> None:
    if _has_table("directory_aliases"):
        op.drop_index(op.f("ix_directory_aliases_kind"), table_name="directory_aliases")
        op.drop_index(op.f("ix_directory_aliases_entry_id"), table_name="directory_aliases")
        op.drop_table("directory_aliases")
    if _has_table("directory_entries"):
        op.drop_index(op.f("ix_directory_entries_kind"), table_name="directory_entries")
        op.drop_table("directory_entries")
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        sa.Enum(name="directorykind").drop(bind, checkfirst=True)
