import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
from app.services.telegram_auth import validate_init_data

BOT_TOKEN = "123456:telegram-test-token"


def build_init_data(auth_date: int, user: dict | None = None) -> str:
    pairs = {
        "auth_date": str(auth_date),
        "query_id": "AAE-test",
        "user": json.dumps(user or {"id": 1234, "first_name": "Test"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_valid_telegram_init_data(monkeypatch):
    monkeypatch.setattr("app.services.telegram_auth.time.time", lambda: 2_000)
    user = validate_init_data(build_init_data(1_950), BOT_TOKEN, 100)
    assert user["id"] == 1234


@pytest.mark.parametrize("auth_date", [0, 1_899, 2_061])
def test_invalid_telegram_auth_date(monkeypatch, auth_date):
    monkeypatch.setattr("app.services.telegram_auth.time.time", lambda: 2_000)
    with pytest.raises(ValueError):
        validate_init_data(build_init_data(auth_date), BOT_TOKEN, 100)
