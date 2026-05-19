from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


settings = get_settings()
database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()


def run_lightweight_migrations() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "users" in table_names and database_url.startswith("postgresql"):
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT"))

    if "events" not in table_names:
        return

    event_columns = {column["name"] for column in inspector.get_columns("events")}
    if "image_url" not in event_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE events ADD COLUMN image_url VARCHAR(500)"))
    if "image_content" not in event_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE events ADD COLUMN image_content BYTEA"))
    if "image_content_type" not in event_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE events ADD COLUMN image_content_type VARCHAR(80)"))
    if "is_republic_championship" not in event_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE events ADD COLUMN is_republic_championship BOOLEAN DEFAULT FALSE NOT NULL"))

    if "nominations" in table_names:
        nomination_columns = {column["name"] for column in inspector.get_columns("nominations")}
        if "battle_type" not in nomination_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE nominations ADD COLUMN battle_type VARCHAR(20) DEFAULT 'solo' NOT NULL"))
