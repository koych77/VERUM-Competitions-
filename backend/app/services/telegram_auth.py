import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> dict:
    if not bot_token:
        raise ValueError("BOT_TOKEN is required to validate Telegram initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise ValueError("Telegram initData hash is missing")

    try:
        auth_date = int(pairs.get("auth_date", "0") or 0)
    except ValueError as exc:
        raise ValueError("Telegram initData auth_date is invalid") from exc
    now = time.time()
    if auth_date <= 0:
        raise ValueError("Telegram initData auth_date is missing")
    if auth_date > now + 60:
        raise ValueError("Telegram initData auth_date is in the future")
    if now - auth_date > max_age_seconds:
        raise ValueError("Telegram initData is expired")

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Telegram initData hash is invalid")

    user_raw = pairs.get("user")
    if not user_raw:
        raise ValueError("Telegram initData user is missing")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Telegram initData user is invalid") from exc
    if not isinstance(user, dict) or not isinstance(user.get("id"), int) or user["id"] <= 0:
        raise ValueError("Telegram initData user is invalid")
    return user
