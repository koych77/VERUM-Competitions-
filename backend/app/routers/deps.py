from fastapi import Header, HTTPException, Query

from app.config import get_settings


def _require_admin_id(telegram_id: int | None) -> int:
    if telegram_id is None:
        raise HTTPException(status_code=401, detail="Не указан Telegram ID администратора")
    if telegram_id not in get_settings().admin_id_set:
        raise HTTPException(status_code=403, detail="Нет доступа к админке")
    return telegram_id


def require_admin(x_telegram_id: int | None = Header(default=None)) -> int:
    return _require_admin_id(x_telegram_id)


def require_admin_download(
    x_telegram_id: int | None = Header(default=None),
    admin_id: int | None = Query(default=None),
) -> int:
    return _require_admin_id(x_telegram_id if x_telegram_id is not None else admin_id)
