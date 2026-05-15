from collections.abc import Sequence
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session, object_session

from app.models import Event, Gender, GenderRule, Nomination, Registration, RegistrationNomination
from app.services.age import calculate_event_age


def ensure_event_open(event: Event, today: date | None = None) -> None:
    today = today or date.today()
    if event.status.value != "open":
        raise HTTPException(status_code=400, detail="Регистрация на мероприятие закрыта")
    if today < event.registration_opens_at or today > event.registration_closes_at:
        raise HTTPException(status_code=400, detail="Регистрация недоступна по датам мероприятия")


def get_available_nominations(
    db: Session,
    event: Event,
    birth_date: date,
    gender: Gender,
) -> list[Nomination]:
    age = calculate_event_age(birth_date, event.event_date, event.is_republic_championship)
    return (
        db.query(Nomination)
        .filter(
            Nomination.event_id == event.id,
            Nomination.is_active.is_(True),
            Nomination.min_age <= age,
            Nomination.max_age >= age,
            Nomination.gender_rule.in_([GenderRule.any, GenderRule(gender.value)]),
        )
        .order_by(Nomination.sort_order, Nomination.title)
        .all()
    )


def validate_nomination_ids(
    db: Session,
    event: Event,
    birth_date: date,
    gender: Gender,
    nomination_ids: Sequence[int],
) -> list[Nomination]:
    if not nomination_ids:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну номинацию")

    available = get_available_nominations(db, event, birth_date, gender)
    available_by_id = {item.id: item for item in available}
    missing = [item_id for item_id in nomination_ids if item_id not in available_by_id]
    if missing:
        raise HTTPException(status_code=400, detail="Одна или несколько номинаций недоступны участнику")

    return [available_by_id[item_id] for item_id in dict.fromkeys(nomination_ids)]


def replace_registration_nominations(registration: Registration, nominations: Sequence[Nomination]) -> None:
    unique_nominations = list({nomination.id: nomination for nomination in nominations}.values())
    session = object_session(registration)
    if registration.id and session is not None:
        session.query(RegistrationNomination).filter(
            RegistrationNomination.registration_id == registration.id,
        ).delete(synchronize_session=False)
        session.flush()
        registration.nominations = []
    else:
        registration.nominations.clear()
    for nomination in unique_nominations:
        registration.nominations.append(RegistrationNomination(nomination_id=nomination.id))
