import pytest
from app.services.sessions import (
    SessionTokenError,
    issue_session_token,
    verify_session_token,
)

SECRET = "test-session-secret-with-at-least-32-characters"


def test_session_round_trip():
    token, expires_at = issue_session_token(7, 123456789, SECRET, 600, now=1_000)
    identity = verify_session_token(token, SECRET, now=1_001)

    assert identity.user_id == 7
    assert identity.telegram_id == 123456789
    assert identity.expires_at == expires_at == 1_600


def test_session_rejects_tampering_and_expiration():
    token, _ = issue_session_token(7, 123456789, SECRET, 60, now=1_000)

    with pytest.raises(SessionTokenError):
        verify_session_token(f"{token}x", SECRET, now=1_001)
    with pytest.raises(SessionTokenError, match="истекла"):
        verify_session_token(token, SECRET, now=1_061)
