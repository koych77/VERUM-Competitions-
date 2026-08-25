import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).resolve().parents[1] / ".test_verum.db"
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["ADMIN_IDS"] = "1001"
os.environ["BOT_TOKEN"] = ""
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SESSION_SECRET"] = "test-session-secret-with-at-least-32-characters"
os.environ["WEBAPP_URL"] = "http://127.0.0.1:8000"

from app.database import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def test_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def login_headers(client: TestClient, telegram_id: int) -> dict[str, str]:
    response = client.post(
        "/api/auth/dev",
        json={
            "telegram_id": telegram_id,
            "telegram_username": f"user_{telegram_id}",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client):
    return login_headers(client, 1001)


@pytest.fixture()
def user_headers(client):
    return login_headers(client, 2001)
