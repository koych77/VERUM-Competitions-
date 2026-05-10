import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import get_settings

logger = logging.getLogger(__name__)


def build_dispatcher() -> Dispatcher:
    settings = get_settings()
    dispatcher = Dispatcher()

    @dispatcher.message(CommandStart())
    async def start(message: types.Message) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Открыть регистрацию VERUM",
                        web_app=WebAppInfo(url=settings.webapp_url),
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
