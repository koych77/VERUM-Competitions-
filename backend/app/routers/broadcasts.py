import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.routers.deps import require_admin

router = APIRouter(prefix="/api/admin/broadcasts", tags=["broadcasts"])

REGISTRATION_FIXED_MESSAGE = """Уважаемые участники!

Приносим извинения за техническую ошибку, из-за которой у некоторых пользователей регистрация могла не сохраниться.

Проблема уже исправлена. Теперь вы можете снова открыть бот и пройти регистрацию на мероприятие.

Пожалуйста, если после нажатия кнопки регистрации вы не увидели подтверждение, заполните заявку повторно.

Спасибо за понимание!"""


@router.post("/registration-fixed", dependencies=[Depends(require_admin)])
async def send_registration_fixed_broadcast(db: Session = Depends(get_db)) -> dict[str, int]:
    settings = get_settings()
    if not settings.bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN не настроен")

    telegram_ids = [
        row.telegram_id
        for row in db.query(User.telegram_id).filter(User.telegram_id.isnot(None)).order_by(User.id).all()
    ]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть регистрацию VERUM",
                    web_app=WebAppInfo(url=settings.normalized_webapp_url),
                )
            ]
        ]
    )

    sent = 0
    failed = 0
    blocked = 0
    bot = Bot(settings.bot_token)
    try:
        for telegram_id in telegram_ids:
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=REGISTRATION_FIXED_MESSAGE,
                    reply_markup=keyboard,
                )
                sent += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=REGISTRATION_FIXED_MESSAGE,
                        reply_markup=keyboard,
                    )
                    sent += 1
                except TelegramAPIError:
                    failed += 1
            except (TelegramForbiddenError, TelegramBadRequest):
                blocked += 1
            except TelegramAPIError:
                failed += 1
            await asyncio.sleep(0.035)
    finally:
        await bot.session.close()

    return {
        "total": len(telegram_ids),
        "sent": sent,
        "blocked": blocked,
        "failed": failed,
    }
