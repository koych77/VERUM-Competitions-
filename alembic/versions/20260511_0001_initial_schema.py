"""initial schema

Revision ID: 20260511_0001
Revises:
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("telegram_username", sa.String(length=255), nullable=True),
            sa.Column("first_name", sa.String(length=255), nullable=True),
            sa.Column("last_name", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)

    if "events" not in existing_tables:
        op.create_table(
            "events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("event_date", sa.Date(), nullable=False),
            sa.Column("place", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("image_url", sa.String(length=500), nullable=True),
            sa.Column("image_content", sa.LargeBinary(), nullable=True),
            sa.Column("image_content_type", sa.String(length=80), nullable=True),
            sa.Column("registration_opens_at", sa.Date(), nullable=False),
            sa.Column("registration_closes_at", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("is_republic_championship", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("allow_full_registration", sa.Boolean(), nullable=False),
            sa.Column("allow_short_registration", sa.Boolean(), nullable=False),
            sa.Column("allow_coach_registration", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "participant_profiles" not in existing_tables:
        op.create_table(
            "participant_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("nickname", sa.String(length=120), nullable=False),
            sa.Column("birth_date", sa.Date(), nullable=False),
            sa.Column("gender", sa.String(length=20), nullable=False),
            sa.Column("phone", sa.String(length=80), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=False),
            sa.Column("club", sa.String(length=160), nullable=False),
            sa.Column("trainer", sa.String(length=160), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )

    if "coach_profiles" not in existing_tables:
        op.create_table(
            "coach_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=80), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=False),
            sa.Column("club", sa.String(length=160), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )

    if "students" not in existing_tables:
        op.create_table(
            "students",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("coach_id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("nickname", sa.String(length=120), nullable=False),
            sa.Column("birth_date", sa.Date(), nullable=False),
            sa.Column("gender", sa.String(length=20), nullable=False),
            sa.Column("city", sa.String(length=120), nullable=False),
            sa.Column("club", sa.String(length=160), nullable=False),
            sa.Column("trainer", sa.String(length=160), nullable=False),
            sa.Column("is_archived", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["coach_id"], ["coach_profiles.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_students_coach_id"), "students", ["coach_id"], unique=False)

    if "nominations" not in existing_tables:
        op.create_table(
            "nominations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("min_age", sa.Integer(), nullable=False),
            sa.Column("max_age", sa.Integer(), nullable=False),
            sa.Column("gender_rule", sa.String(length=20), nullable=False),
            sa.Column("experience", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_nominations_event_id"), "nominations", ["event_id"], unique=False)

    if "registrations" not in existing_tables:
        op.create_table(
            "registrations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("registration_type", sa.String(length=20), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("participant_profile_id", sa.Integer(), nullable=True),
            sa.Column("coach_id", sa.Integer(), nullable=True),
            sa.Column("student_id", sa.Integer(), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("nickname", sa.String(length=120), nullable=False),
            sa.Column("birth_date", sa.Date(), nullable=False),
            sa.Column("age_on_event", sa.Integer(), nullable=False),
            sa.Column("gender", sa.String(length=20), nullable=False),
            sa.Column("phone", sa.String(length=80), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("club", sa.String(length=160), nullable=True),
            sa.Column("trainer", sa.String(length=160), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["coach_id"], ["coach_profiles.id"]),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
            sa.ForeignKeyConstraint(["participant_profile_id"], ["participant_profiles.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_id", "participant_profile_id", name="uq_event_profile_registration"),
            sa.UniqueConstraint("event_id", "student_id", name="uq_event_student_registration"),
        )
        op.create_index(op.f("ix_registrations_event_id"), "registrations", ["event_id"], unique=False)
        op.create_index(op.f("ix_registrations_user_id"), "registrations", ["user_id"], unique=False)

    if "registration_nominations" not in existing_tables:
        op.create_table(
            "registration_nominations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("registration_id", sa.Integer(), nullable=False),
            sa.Column("nomination_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["nomination_id"], ["nominations.id"]),
            sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("registration_id", "nomination_id", name="uq_registration_nomination"),
        )
        op.create_index(
            op.f("ix_registration_nominations_nomination_id"),
            "registration_nominations",
            ["nomination_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_registration_nominations_registration_id"),
            "registration_nominations",
            ["registration_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("registration_nominations")
    op.drop_table("registrations")
    op.drop_table("nominations")
    op.drop_table("students")
    op.drop_table("coach_profiles")
    op.drop_table("participant_profiles")
    op.drop_table("events")
    op.drop_table("users")
