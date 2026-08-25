import asyncio
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.models import BroadcastDelivery, Registration, RegistrationNomination, RegistrationType, User
from app.routers.deps import require_admin

router = APIRouter(prefix="/api/admin/broadcasts", tags=["broadcasts"])
CAMPAIGN_KEY = "registration-fixed-v1"
DELIVERY_CLAIM_TTL = timedelta(minutes=15)

MESSAGE_INTRO = """Уважаемые участники!

Сообщаем, что технические ошибки, из-за которых у некоторых пользователей регистрация могла не сохраниться, устранены.

Если ранее у вас не получилось завершить регистрацию или после отправки заявки не появилось подтверждение, пожалуйста, откройте бот и зарегистрируйтесь снова.

Если ваша регистрация уже есть в списке ниже, переживать не нужно — данные сохранены."""

MESSAGE_FOOTER = "Спасибо за понимание!"


def _registration_type_label(registration_type: RegistrationType) -> str:
    return {
        RegistrationType.full: "полная регистрация",
        RegistrationType.short: "короткая регистрация",
        RegistrationType.coach: "регистрация тренером",
    }.get(registration_type, registration_type.value)


def _build_user_message(user: User) -> str:
    registrations = sorted(
        user_registrations_with_event(user),
        key=lambda item: (item.event.event_date, item.event.title, item.full_name),
    )
    if not registrations:
        return f"""{MESSAGE_INTRO}

По вашему Telegram-аккаунту сохраненных регистраций пока не найдено. Если вы пытались зарегистрироваться и не увидели подтверждение, пожалуйста, заполните заявку повторно.

{MESSAGE_FOOTER}"""

    lines = [
        MESSAGE_INTRO,
        "",
        "Ваши сохраненные регистрации:",
    ]
    for registration in registrations:
        nomination_titles = [item.nomination.title for item in registration.nominations if item.nomination]
        nominations_text = ", ".join(nomination_titles) if nomination_titles else "номинации не выбраны"
        lines.extend(
            [
                "",
                f"Мероприятие: {registration.event.title}",
                f"Участник: {registration.full_name} / {registration.nickname}",
                f"Тип: {_registration_type_label(registration.registration_type)}",
                f"Номинации: {nominations_text}",
            ]
        )
    lines.extend(["", MESSAGE_FOOTER])
    return "\n".join(lines)


def user_registrations_with_event(user: User) -> list[Registration]:
    return [
        registration
        for registration in user.broadcast_registrations
        if registration.event is not None
    ]


def _split_message(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        next_part = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(next_part) <= limit:
            current = next_part
            continue
        if current:
            chunks.append(current)
            current = paragraph
        while len(current) > limit:
            chunks.append(current[:limit])
            current = current[limit:]
    if current:
        chunks.append(current)
    return chunks


def _broadcast_users(db: Session) -> list[User]:
    return (
        db.query(User)
        .options(
            joinedload(User.broadcast_registrations)
            .joinedload(Registration.nominations)
            .joinedload(RegistrationNomination.nomination),
            joinedload(User.broadcast_registrations).joinedload(Registration.event),
        )
        .filter(User.telegram_id.isnot(None))
        .order_by(User.id)
        .all()
    )


def _claim_delivery(db: Session, user: User) -> tuple[BroadcastDelivery | None, str]:
    now = datetime.now(UTC).replace(tzinfo=None)
    delivery = (
        db.query(BroadcastDelivery)
        .filter(BroadcastDelivery.campaign_key == CAMPAIGN_KEY, BroadcastDelivery.user_id == user.id)
        .one_or_none()
    )
    if delivery and delivery.status in {"sent", "blocked"}:
        return None, delivery.status
    if delivery and delivery.status == "sending" and delivery.updated_at > now - DELIVERY_CLAIM_TTL:
        return None, "in_progress"

    if delivery is None:
        delivery = BroadcastDelivery(
            campaign_key=CAMPAIGN_KEY,
            user_id=user.id,
            status="sending",
            attempts=1,
            parts_sent=0,
        )
        db.add(delivery)
    else:
        delivery.status = "sending"
        delivery.attempts += 1
        delivery.last_error = None
        delivery.updated_at = now
    try:
        db.commit()
        db.refresh(delivery)
    except IntegrityError:
        db.rollback()
        return None, "in_progress"
    return delivery, "claimed"


@router.get("/registration-fixed/preview", dependencies=[Depends(require_admin)])
def preview_registration_fixed_broadcast(db: Session = Depends(get_db)) -> dict[str, int | str]:
    users = _broadcast_users(db)
    deliveries = (
        db.query(BroadcastDelivery)
        .filter(BroadcastDelivery.campaign_key == CAMPAIGN_KEY)
        .all()
    )
    statuses = {delivery.user_id: delivery.status for delivery in deliveries}
    terminal = sum(statuses.get(user.id) in {"sent", "blocked"} for user in users)
    return {
        "campaign_key": CAMPAIGN_KEY,
        "total": len(users),
        "already_processed": terminal,
        "pending": len(users) - terminal,
        "sample_message": _build_user_message(users[0]) if users else MESSAGE_INTRO,
    }


@router.post("/registration-fixed", dependencies=[Depends(require_admin)])
async def send_registration_fixed_broadcast(db: Session = Depends(get_db)) -> dict[str, int]:
    settings = get_settings()
    if not settings.bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN не настроен")

    users = _broadcast_users(db)
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
    skipped = 0
    bot = Bot(settings.bot_token)
    try:
        for user in users:
            message_parts = _split_message(_build_user_message(user))
            delivery, _ = _claim_delivery(db, user)
            if delivery is None:
                skipped += 1
                continue
            try:
                for index in range(min(delivery.parts_sent, len(message_parts)), len(message_parts)):
                    message_part = message_parts[index]
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_part,
                            reply_markup=keyboard if index == len(message_parts) - 1 else None,
                        )
                    except TelegramRetryAfter as exc:
                        await asyncio.sleep(exc.retry_after)
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_part,
                            reply_markup=keyboard if index == len(message_parts) - 1 else None,
                        )
                    delivery.parts_sent = index + 1
                    delivery.updated_at = datetime.now(UTC).replace(tzinfo=None)
                    db.commit()
                delivery.status = "sent"
                delivery.last_error = None
                db.commit()
                sent += 1
            except (TelegramForbiddenError, TelegramBadRequest):
                delivery.status = "blocked"
                delivery.last_error = "telegram_unavailable"
                db.commit()
                blocked += 1
            except TelegramAPIError as exc:
                delivery.status = "failed"
                delivery.last_error = type(exc).__name__[:160]
                db.commit()
                failed += 1
            await asyncio.sleep(0.035)
    finally:
        await bot.session.close()

    return {
        "total": len(users),
        "sent": sent,
        "blocked": blocked,
        "failed": failed,
        "skipped": skipped,
    }
