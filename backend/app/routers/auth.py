from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import TelegramUserIn, UserOut
from app.services.telegram_auth import validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])


class InitDataIn(BaseModel):
    init_data: str


def upsert_user(db: Session, data: TelegramUserIn) -> User:
    user = db.query(User).filter(User.telegram_id == data.telegram_id).one_or_none()
    if user is None:
        user = User(telegram_id=data.telegram_id)
        db.add(user)
    user.telegram_username = data.telegram_username
    user.first_name = data.first_name
    user.last_name = data.last_name
    db.commit()
    db.refresh(user)
    return user


@router.post("/dev", response_model=UserOut)
def dev_login(payload: TelegramUserIn, db: Session = Depends(get_db)) -> UserOut:
    settings = get_settings()
    user = upsert_user(db, payload)
    return UserOut.model_validate(user).model_copy(update={"is_admin": payload.telegram_id in settings.admin_id_set})


@router.post("/telegram", response_model=UserOut)
def telegram_login(payload: InitDataIn, db: Session = Depends(get_db)) -> UserOut:
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
    return UserOut.model_validate(user).model_copy(update={"is_admin": user.telegram_id in settings.admin_id_set})
