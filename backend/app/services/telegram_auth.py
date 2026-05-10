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

    auth_date = int(pairs.get("auth_date", "0") or 0)
    if auth_date and time.time() - auth_date > max_age_seconds:
        raise ValueError("Telegram initData is expired")

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Telegram initData hash is invalid")

    user_raw = pairs.get("user")
    return json.loads(user_raw) if user_raw else {}
