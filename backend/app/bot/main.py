import asyncio
import hashlib
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo

from app.config import get_settings
from app.database import SessionLocal
from app.models import User

logger = logging.getLogger(__name__)

bot: Bot | None = None
dispatcher: Dispatcher | None = None


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


def is_webhook_enabled() -> bool:
    settings = get_settings()
    return bool(settings.bot_token and settings.normalized_webapp_url.startswith("https://"))


def webhook_path() -> str:
    settings = get_settings()
    digest = hashlib.sha256(settings.bot_token.encode("utf-8")).hexdigest()[:32]
    return f"/api/bot/webhook/{digest}"


def webhook_secret() -> str:
    settings = get_settings()
    return hashlib.sha256(f"{settings.bot_token}:verum-webhook".encode("utf-8")).hexdigest()


def get_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    global bot, dispatcher
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is empty")
    if bot is None:
        bot = Bot(settings.bot_token)
    if dispatcher is None:
        dispatcher = build_dispatcher()
    return bot, dispatcher


async def setup_bot_webhook() -> None:
    settings = get_settings()
    if not is_webhook_enabled():
        return
    current_bot, _ = get_bot_and_dispatcher()
    webhook_url = f"{settings.normalized_webapp_url}{webhook_path()}"
    await current_bot.set_webhook(
        webhook_url,
        secret_token=webhook_secret(),
        drop_pending_updates=False,
    )
    logger.info("Telegram bot webhook is enabled: %s", webhook_url)


async def feed_webhook_update(payload: dict) -> None:
    current_bot, current_dispatcher = get_bot_and_dispatcher()
    update = Update.model_validate(payload, context={"bot": current_bot})
    await current_dispatcher.feed_update(current_bot, update)


async def run_bot_polling() -> None:
    settings = get_settings()
    if not settings.bot_token:
        logger.warning("BOT_TOKEN is empty, Telegram bot polling is disabled")
        return
    if is_webhook_enabled():
        logger.info("Telegram bot polling is disabled because webhook mode is enabled")
        return
    current_bot, current_dispatcher = get_bot_and_dispatcher()
    await current_bot.delete_webhook(drop_pending_updates=False)
    await current_dispatcher.start_polling(current_bot)


def start_bot_background_task() -> asyncio.Task | None:
    settings = get_settings()
    if not settings.bot_token:
        return None
    if is_webhook_enabled():
        return None
    return asyncio.create_task(run_bot_polling())


async def shutdown_bot() -> None:
    global bot
    if bot is not None:
        await bot.session.close()
        bot = None
