from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import AuthSessionOut, TelegramUserIn
from app.services.sessions import issue_session_token
from app.services.telegram_auth import validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])


class InitDataIn(BaseModel):
    init_data: str


def upsert_user(db: Session, data: TelegramUserIn, *, commit: bool = True) -> User:
    user = db.query(User).filter(User.telegram_id == data.telegram_id).one_or_none()
    if user is None:
        user = User(telegram_id=data.telegram_id)
        db.add(user)
    user.telegram_username = data.telegram_username
    user.first_name = data.first_name
    user.last_name = data.last_name
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def _session_response(user: User) -> AuthSessionOut:
    settings = get_settings()
    access_token, expires_at = issue_session_token(
        user.id,
        user.telegram_id,
        settings.session_signing_key,
        settings.session_ttl_seconds,
    )
    return AuthSessionOut(
        id=user.id,
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_admin=user.telegram_id in settings.admin_id_set,
        access_token=access_token,
        expires_at=expires_at,
    )


@router.post("/dev", response_model=AuthSessionOut)
def dev_login(payload: TelegramUserIn, db: Session = Depends(get_db)) -> AuthSessionOut:
    settings = get_settings()
    if not settings.allow_dev_auth or settings.is_production:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    if payload.telegram_id <= 0:
        raise HTTPException(status_code=400, detail="Некорректный Telegram ID")
    return _session_response(upsert_user(db, payload))


@router.post("/telegram", response_model=AuthSessionOut)
def telegram_login(payload: InitDataIn, db: Session = Depends(get_db)) -> AuthSessionOut:
    settings = get_settings()
    try:
        telegram_user = validate_init_data(
            payload.init_data,
            settings.bot_token,
            settings.telegram_init_data_ttl_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_in = TelegramUserIn(
        telegram_id=telegram_user["id"],
        telegram_username=telegram_user.get("username"),
        first_name=telegram_user.get("first_name"),
        last_name=telegram_user.get("last_name"),
    )
    user = upsert_user(db, user_in)
    return _session_response(user)
