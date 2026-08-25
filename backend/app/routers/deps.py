from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.services.sessions import SessionTokenError, verify_session_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    settings = get_settings()
    try:
        identity = verify_session_token(credentials.credentials, settings.session_signing_key)
    except SessionTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, identity.user_id)
    if user is None or user.telegram_id != identity.telegram_id:
        raise HTTPException(status_code=401, detail="Сессия больше недействительна")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.telegram_id not in get_settings().admin_id_set:
        raise HTTPException(status_code=403, detail="Нет доступа к админке")
    return current_user


def require_admin_download(current_user: User = Depends(require_admin)) -> User:
    return current_user


def require_self_or_admin(current_user: User, telegram_id: int) -> None:
    if current_user.telegram_id != telegram_id and current_user.telegram_id not in get_settings().admin_id_set:
        raise HTTPException(status_code=403, detail="Нет доступа к данным другого пользователя")
