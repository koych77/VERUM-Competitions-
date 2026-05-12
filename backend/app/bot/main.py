import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import get_settings
from app.database import SessionLocal
from app.models import User

logger = logging.getLogger(__name__)


def remember_user(message: types.Message) -> None:
    if message.from_user is None:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).one_or_none()
        if user is None:
            user = User(telegram_id=message.from_user.id)
            db.add(user)
        user.telegram_username = message.from_user.username
        user.first_name = message.from_user.first_name
        user.last_name = message.from_user.last_name
        db.commit()
    finally:
        db.close()


def build_dispatcher() -> Dispatcher:
    settings = get_settings()
    dispatcher = Dispatcher()

    @dispatcher.message(CommandStart())
    async def start(message: types.Message) -> None:
        remember_user(message)
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
        await message.answer(
            "Привет! Нажмите кнопку ниже, чтобы открыть регистрацию на мероприятия VERUM.",
            reply_markup=keyboard,
        )

    return dispatcher


async def run_bot_polling() -> None:
    settings = get_settings()
    if not settings.bot_token:
        logger.warning("BOT_TOKEN is empty, Telegram bot polling is disabled")
        return
    bot = Bot(settings.bot_token)
    dispatcher = build_dispatcher()
    await dispatcher.start_polling(bot)


def start_bot_background_task() -> asyncio.Task | None:
    settings = get_settings()
    if not settings.bot_token:
        return None
    return asyncio.create_task(run_bot_polling())
