import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class SessionTokenError(ValueError):
    pass


@dataclass(frozen=True)
class SessionIdentity:
    user_id: int
    telegram_id: int
    expires_at: int


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(f"{value}{padding}")
    except (ValueError, TypeError) as exc:
        raise SessionTokenError("Некорректная сессия") from exc


def issue_session_token(
    user_id: int,
    telegram_id: int,
    secret: str,
    ttl_seconds: int,
    now: int | None = None,
) -> tuple[str, int]:
    issued_at = int(now if now is not None else time.time())
    expires_at = issued_at + max(60, int(ttl_seconds))
    payload = {
        "exp": expires_at,
        "iat": issued_at,
        "sub": int(user_id),
        "tid": int(telegram_id),
        "v": 1,
    }
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_encode(signature)}", expires_at


def verify_session_token(token: str, secret: str, now: int | None = None) -> SessionIdentity:
    if not token or len(token) > 2048:
        raise SessionTokenError("Некорректная сессия")
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
    except ValueError as exc:
        raise SessionTokenError("Некорректная сессия") from exc

    expected = hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    received = _decode(encoded_signature)
    if not hmac.compare_digest(expected, received):
        raise SessionTokenError("Некорректная сессия")

    try:
        payload = json.loads(_decode(encoded_payload))
        user_id = int(payload["sub"])
        telegram_id = int(payload["tid"])
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        version = int(payload["v"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SessionTokenError("Некорректная сессия") from exc

    current_time = int(now if now is not None else time.time())
    if version != 1 or user_id <= 0 or telegram_id <= 0:
        raise SessionTokenError("Некорректная сессия")
    if issued_at > current_time + 60:
        raise SessionTokenError("Некорректное время сессии")
    if expires_at <= current_time:
        raise SessionTokenError("Сессия истекла")
    return SessionIdentity(user_id=user_id, telegram_id=telegram_id, expires_at=expires_at)
