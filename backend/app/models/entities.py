import enum
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Gender(str, enum.Enum):
    male = "male"
    female = "female"


class GenderRule(str, enum.Enum):
    male = "male"
    female = "female"
    any = "any"


class EventStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    closed = "closed"
    archived = "archived"


class RegistrationType(str, enum.Enum):
    full = "full"
    short = "short"
    coach = "coach"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    participant_profile: Mapped["ParticipantProfile | None"] = relationship(back_populates="user")
    coach_profile: Mapped["CoachProfile | None"] = relationship(back_populates="user")


class ParticipantProfile(Base):
    __tablename__ = "participant_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(120))
    birth_date: Mapped[date] = mapped_column(Date)
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str] = mapped_column(String(120))
    club: Mapped[str] = mapped_column(String(160))
    trainer: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="participant_profile")


class CoachProfile(Base):
    __tablename__ = "coach_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str] = mapped_column(String(120))
    club: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="coach_profile")
    students: Mapped[list["Student"]] = relationship(back_populates="coach")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coach_profiles.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(120))
    birth_date: Mapped[date] = mapped_column(Date)
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    city: Mapped[str] = mapped_column(String(120))
    club: Mapped[str] = mapped_column(String(160))
    trainer: Mapped[str] = mapped_column(String(160))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    coach: Mapped[CoachProfile] = relationship(back_populates="students")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    event_date: Mapped[date] = mapped_column(Date)
    place: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    registration_opens_at: Mapped[date] = mapped_column(Date)
    registration_closes_at: Mapped[date] = mapped_column(Date)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.draft)
    is_republic_championship: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_full_registration: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_short_registration: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_coach_registration: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nominations: Mapped[list["Nomination"]] = relationship(back_populates="event")


class Nomination(Base):
    __tablename__ = "nominations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    min_age: Mapped[int] = mapped_column(Integer)
    max_age: Mapped[int] = mapped_column(Integer)
    gender_rule: Mapped[GenderRule] = mapped_column(Enum(GenderRule), default=GenderRule.any)
    experience: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    event: Mapped[Event] = relationship(back_populates="nominations")


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "participant_profile_id", name="uq_event_profile_registration"),
        UniqueConstraint("event_id", "student_id", name="uq_event_student_registration"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    registration_type: Mapped[RegistrationType] = mapped_column(Enum(RegistrationType))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    participant_profile_id: Mapped[int | None] = mapped_column(ForeignKey("participant_profiles.id"), nullable=True)
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coach_profiles.id"), nullable=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(120))
    birth_date: Mapped[date] = mapped_column(Date)
    age_on_event: Mapped[int] = mapped_column(Integer)
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    club: Mapped[str | None] = mapped_column(String(160), nullable=True)
    trainer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event: Mapped[Event] = relationship()
    nominations: Mapped[list["RegistrationNomination"]] = relationship(
        back_populates="registration",
        cascade="all, delete-orphan",
    )


class RegistrationNomination(Base):
    __tablename__ = "registration_nominations"
    __table_args__ = (UniqueConstraint("registration_id", "nomination_id", name="uq_registration_nomination"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), index=True)
    nomination_id: Mapped[int] = mapped_column(ForeignKey("nominations.id"), index=True)

    registration: Mapped[Registration] = relationship(back_populates="nominations")
    nomination: Mapped[Nomination] = relationship()
