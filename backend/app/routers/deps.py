from fastapi import Header, HTTPException

from app.config import get_settings


def require_admin(x_telegram_id: int | None = Header(default=None)) -> int:
    if x_telegram_id is None:
        raise HTTPException(status_code=401, detail="Не указан Telegram ID администратора")
    if x_telegram_id not in get_settings().admin_id_set:
        raise HTTPException(status_code=403, detail="Нет доступа к админке")
    return x_telegram_id
